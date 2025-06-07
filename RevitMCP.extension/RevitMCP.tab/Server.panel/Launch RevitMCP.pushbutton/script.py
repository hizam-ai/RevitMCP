# RevitMCP: This script runs in pyRevit (IronPython). Use Python 2.7 syntax (no f-strings, use 'except Exception, e:').
#!/usr/bin/python
# -*- coding: UTF-8 -*-
"""Starts the RevitMCP Standalone Server."""

# pyRevit automatically adds the extension's 'lib' folder to sys.path.
# Modules (RevitMCP_RevitListener, RevitMCP_UI) placed in 'lib' are directly importable.

print("pyRevit Button: Launch RevitMCP - Attempting to load UI manager...")

import sys
import os
import subprocess
import traceback
from pyrevit import script

def start_standalone_server():
    """
    Finds and starts the standalone_mcp_server.py in a new CPython process.
    """
    logger = script.get_logger()
    logger.info("Attempting to launch the standalone MCP server...")

    try:
        # Construct the path to the standalone server script
        ext_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        server_script_path = os.path.join(ext_dir, 'lib', 'RevitMCP_ExternalServer', 'standalone_mcp_server.py')

        if not os.path.exists(server_script_path):
            logger.error("Standalone server script not found at: {}".format(server_script_path))
            from pyrevit import forms
            forms.alert("Error: standalone_mcp_server.py not found!", title="RevitMCP")
            return

        # Find a suitable python executable with a more robust method.
        python_path = None
        
        # Method 1: Check if pyRevit's sys.executable is available and points to IronPython.
        if sys.executable and 'ipy' in os.path.basename(sys.executable).lower():
            potential_path = sys.executable.replace("ipy.exe", "python.exe")
            if os.path.exists(potential_path):
                python_path = potential_path
                logger.info("Found CPython executable alongside IronPython: {}".format(python_path))

        # Method 2: If the first method fails, fall back to 'python' and hope it's in the system's PATH.
        if not python_path:
            python_path = "python"
            logger.info("Could not find CPython executable beside IronPython. Falling back to 'python' in PATH.")

        logger.info("Found server script: {}".format(server_script_path))
        logger.info("Using Python executable: {}".format(python_path))
        
        # Launch the server in a new console window
        # This allows its logs to be visible and keeps it independent of Revit's process
        creation_flags = subprocess.CREATE_NEW_CONSOLE
        subprocess.Popen([python_path, "-u", server_script_path], creationflags=creation_flags)
        
        logger.info("Standalone server process has been launched.")
        from pyrevit import forms
        forms.alert(
            "RevitMCP Standalone Server has been launched in a new console window. "
            "It is now ready to accept connections.",
            title="RevitMCP Server Started"
        )

    except Exception as e:
        logger.error("Failed to launch standalone server.")
        logger.error(traceback.format_exc())
        from pyrevit import forms
        forms.alert(
            "An unexpected error occurred while launching the server:\n\n{}".format(e),
            title="RevitMCP Launch Error"
        )

if __name__ == "__main__":
    start_standalone_server()
