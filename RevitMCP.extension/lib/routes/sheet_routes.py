# RevitMCP: Routes for managing External Events
# -*- coding: UTF-8 -*-

from pyrevit import routes, script
import sys
import os

def register_routes(api):
    """
    Register routes for triggering and checking external events.
    These are called by the standalone MCP server.
    """
    logger = script.get_logger()

    # Ensure the lib/RevitMCP_Tools path is available
    lib_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'RevitMCP_Tools')
    if lib_dir not in sys.path:
        sys.path.append(lib_dir)

    @api.route('/external_events/trigger', methods=['POST'])
    def handle_trigger_event(request):
        """
        Triggers a general-purpose external event.
        Payload: {"operation": "...", "params": {...}}
        """
        try:
            from external_event_handler import trigger_event
            
            payload = request.data
            operation = payload.get('operation')
            params = payload.get('params', {})

            if not operation:
                return routes.Response(status=400, data={'error': "Missing 'operation' in request"})
            
            logger.info("Route: Triggering event for operation '{}'".format(operation))
            result = trigger_event(operation, params)
            return result

        except Exception as e:
            logger.error("Route Error on /trigger: {}".format(e), exc_info=True)
            return routes.Response(status=500, data={'error': str(e)})

    @api.route('/external_events/status/<event_id>', methods=['GET'])
    def handle_event_status(request, event_id):
        """
        Checks the status of a triggered external event.
        """
        try:
            from external_event_handler import get_event_status
            
            logger.debug("Route: Checking status for event ID '{}'".format(event_id))
            status = get_event_status(event_id)
            
            if status.get('status') == 'not_found':
                return routes.Response(status=404, data=status)
            
            return status

        except Exception as e:
            logger.error("Route Error on /status: {}".format(e), exc_info=True)
            return routes.Response(status=500, data={'error': str(e)})
            
    # Keep the read-only list_views route here as it doesn't need an external event
    @api.route('/sheets/list_views', methods=['GET'])
    def handle_list_views(request):
        """
        List all views in the current document that can be placed on sheets.
        This is a read-only operation and is safe to be handled directly.
        """
        try:
            from pyrevit import DB, revit
            from RevitMCP_Tools.sheet_placement_tool import get_view_type_name # Assuming this is safe
            doc = revit.doc
            
            views = DB.FilteredElementCollector(doc).OfClass(DB.View).ToElements()
            view_list = []
            for view in views:
                if view.IsTemplate or view.ViewType == DB.ViewType.DrawingSheet:
                    continue
                if hasattr(view, 'Name') and view.Name:
                     view_list.append({
                        "name": view.Name,
                        "type": get_view_type_name(view, logger),
                        "id": str(view.Id.IntegerValue)
                    })
            
            return {"views": view_list}
            
        except Exception as e:
            logger.error("Route Error on /list_views: {}".format(e), exc_info=True)
            return routes.Response(status=500, data={'error': str(e)}) 