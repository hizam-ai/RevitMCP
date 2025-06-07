# RevitMCP: Standalone MCP Server (External Process)
# -*- coding: UTF-8 -*-

"""
Proper MCP Server implementation that runs as an external process.
- Serves the Web UI over HTTP.
- Communicates with AI clients via WebSocket (MCP).
- Communicates with Revit via HTTP (triggering External Events).
"""

import json
import asyncio
import websockets
import requests
import time
import os
from typing import Dict, Any
from aiohttp import web
import aiohttp_cors
import aiohttp

class RevitMCPServer:
    """
    Standalone MCP Server for Revit integration.
    """
    
    def __init__(self, revit_port=48884, mcp_port=8001):
        self.revit_port = revit_port
        self.mcp_port = mcp_port
        self.revit_base_url = f"http://localhost:{revit_port}/revit-mcp-v1"
        self.root_dir = os.path.dirname(os.path.abspath(__file__))

    # --- WebSocket (MCP) Methods ---
    async def handle_mcp_request(self, request):
        """Handle incoming MCP requests via WebSocket."""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async for msg in ws:
            if msg.type == web.WSMsgType.TEXT:
                try:
                    mcp_request = json.loads(msg.data)
                    response = await self.process_mcp_request(mcp_request)
                    await ws.send_json(response)
                except Exception as e:
                    error_response = {
                        "jsonrpc": "2.0",
                        "error": {"code": -32603, "message": f"Internal error: {str(e)}"}
                    }
                    await ws.send_json(error_response)
            elif msg.type == web.WSMsgType.ERROR:
                print('WebSocket connection closed with exception %s' % ws.exception())

        return ws

    async def process_mcp_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process MCP JSON-RPC request."""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")
        
        if method == "tools/call":
            return await self.handle_tool_call(params, request_id)
        elif method == "tools/list":
            return self.list_tools(request_id)
        else:
            return {
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }

    def list_tools(self, request_id):
        """List available MCP tools."""
        return {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "place_view_on_sheet",
                        "description": "Places a specified view onto a new sheet in Revit. This is an asynchronous operation.",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "view_name": {"type": "string", "description": "The name of the view to place."},
                                "exact_match": {"type": "boolean", "default": False, "description": "Whether the view name must be an exact match."}
                            },
                            "required": ["view_name"]
                        }
                    },
                    {
                        "name": "list_views", 
                        "description": "Lists all placeable views in the Revit model.",
                        "inputSchema": {"type": "object", "properties": {}}
                    }
                ]
            },
            "id": request_id
        }

    async def handle_tool_call(self, params: Dict[str, Any], request_id):
        """Handle MCP tool call by communicating with Revit."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        try:
            if tool_name == "place_view_on_sheet":
                result = await self.place_view_on_sheet(arguments)
            elif tool_name == "list_views":
                result = await self.list_views()
            else:
                raise ValueError(f"Unknown tool: {tool_name}")
            
            return {"jsonrpc": "2.0", "result": {"content": [{"type": "text", "text": json.dumps(result, indent=2)}]}, "id": request_id}
            
        except Exception as e:
            return {"jsonrpc": "2.0", "error": {"code": -32602, "message": f"Tool execution failed: {str(e)}"},"id": request_id}
            
    # --- Revit Communication Methods ---
    async def place_view_on_sheet(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Triggers the place_view_on_sheet external event in Revit."""
        url = f"{self.revit_base_url}/external_events/trigger"
        payload = {"operation": "place_view_on_sheet", "params": arguments}
        print(f"STANDALONE_SERVER: Sending POST request to {url} with payload: {json.dumps(payload)}")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                timeout=10
            ) as response:
                print(f"STANDALONE_SERVER: Received response {response.status} from Revit.")
                response.raise_for_status()
                result = await response.json()
        
        if result.get("status") == "processing" and result.get("event_id"):
            return await self.wait_for_completion(result["event_id"])
        return result

    async def list_views(self) -> Dict[str, Any]:
        """Lists views by calling the read-only route in Revit."""
        url = f"{self.revit_base_url}/sheets/list_views"
        print(f"STANDALONE_SERVER: Sending GET request to {url}")
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                response.raise_for_status()
                return await response.json()

    async def wait_for_completion(self, event_id: str, timeout: int = 30) -> Dict[str, Any]:
        """Polls Revit for the result of an asynchronous operation."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            await asyncio.sleep(0.5)
            url = f"{self.revit_base_url}/external_events/status/{event_id}"
            print(f"STANDALONE_SERVER: Polling status at {url}")
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("status") in ["completed", "failed"]:
                            return result.get('result', result)
        raise asyncio.TimeoutError("Operation timed out waiting for Revit.")

    # --- HTTP Web UI Methods ---
    async def handle_index(self, request):
        """Serve the main index.html file."""
        index_path = os.path.join(self.root_dir, 'templates', 'index.html')
        return web.FileResponse(index_path)

    def start(self):
        """Starts the combined HTTP and WebSocket server."""
        app = web.Application()
        
        # Configure routes
        app.router.add_get('/', self.handle_index)
        app.router.add_get('/mcp', self.handle_mcp_request)  # WebSocket route
        app.router.add_static('/static', path=os.path.join(self.root_dir, 'static'))
        
        # Configure CORS
        cors = aiohttp_cors.setup(app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*"
            )
        })
        for route in list(app.router.routes()):
            cors.add(route)
            
        print(f"Starting RevitMCP Server at http://localhost:{self.mcp_port}")
        print(f"  - Web UI available at http://localhost:{self.mcp_port}")
        print(f"  - MCP WebSocket at ws://localhost:{self.mcp_port}/mcp")
        web.run_app(app, host='localhost', port=self.mcp_port)


if __name__ == "__main__":
    server = RevitMCPServer()
    server.start() 