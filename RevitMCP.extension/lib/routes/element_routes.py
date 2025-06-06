# RevitMCP: Element-related HTTP routes
# -*- coding: UTF-8 -*-

from pyrevit import routes, script, DB
from System.Collections.Generic import List
import sys
import os

def register_routes(api):
    """Register all element-related routes with the API"""
    
    @api.route('/get_elements_by_category', methods=['POST'])
    def handle_get_elements_by_category(request):
        """
        Handles POST requests to /revit-mcp-v1/get_elements_by_category
        Returns elements in Revit by category name (without selecting them).
        Uses FilteredElementCollector with ToElementIds() for better performance.
        """
        route_logger = script.get_logger()
        
        if not request:
            route_logger.error("Critical error: 'request' object is None.")
            return routes.Response(status=500, data={"error": "Internal server error: 'request' object is None.", "details": "The 'request' object was not provided to the handler by pyRevit."})

        try:
            # Access the JSON payload from the request
            payload = request.data if hasattr(request, 'data') else None
            route_logger.info("Successfully accessed request.data. Type: {}, Value: {}".format(type(payload), payload))

            if not payload or not isinstance(payload, dict):
                route_logger.error("Request body (payload) is missing or not a valid JSON object.")
                return routes.Response(status=400, data={"error": "Request body is missing or not a valid JSON object."})

            category_name_payload = payload.get('category_name')
            
            if not category_name_payload:
                route_logger.error("Missing 'category_name' in JSON body for /get_elements_by_category.")
                return routes.Response(status=400, data={"error": "Missing 'category_name' in JSON request body."})

            # Get document from __revit__
            current_uiapp = __revit__
            if not hasattr(current_uiapp, 'ActiveUIDocument') or not current_uiapp.ActiveUIDocument:
                route_logger.error("Error in /get_elements_by_category: No active UI document.")
                return routes.Response(status=503, data={"error": "No active Revit UI document found."})
            uidoc = current_uiapp.ActiveUIDocument
            doc = uidoc.Document

            # Category validation and element collection
            built_in_category = None
            if hasattr(DB.BuiltInCategory, category_name_payload):
                built_in_category = getattr(DB.BuiltInCategory, category_name_payload)
            else:
                if not category_name_payload.startswith("OST_"):
                    possible_ost_category = "OST_" + category_name_payload.replace(" ", "")
                    if hasattr(DB.BuiltInCategory, possible_ost_category):
                        built_in_category = getattr(DB.BuiltInCategory, possible_ost_category)
                        route_logger.info("Interpreted category '{}' as '{}'.".format(category_name_payload, possible_ost_category))
                    else:
                        route_logger.error("Invalid category_name: '{}'. Not a recognized BuiltInCategory. Try OST_ format.".format(category_name_payload))
                        return routes.Response(status=400, data={"error": "Invalid category_name: '{}'. Not recognized.".format(category_name_payload)})
                else:
                    route_logger.error("Invalid category_name: '{}'. Not a recognized BuiltInCategory.".format(category_name_payload))
                    return routes.Response(status=400, data={"error": "Invalid category_name: '{}'.".format(category_name_payload)})

            # Use ToElementIds() for better performance - no need for ToElements()
            element_ids_collector = DB.FilteredElementCollector(doc)\
                                       .OfCategory(built_in_category)\
                                       .WhereElementIsNotElementType()\
                                       .ToElementIds()
            
            element_ids = []
            route_logger.info("Found {} elements in category '{}' using ToElementIds()".format(element_ids_collector.Count, category_name_payload))
            
            # Convert ElementId objects to string list
            for element_id in element_ids_collector:
                element_ids.append(str(element_id.IntegerValue))

            if not element_ids:
                route_logger.info("No elements found for category '{}' to return.".format(category_name_payload))
                return {"status": "success", "message": "No elements found for category '{}'".format(category_name_payload), "count": 0, "element_ids": []}
            
            route_logger.info("Successfully retrieved {} element IDs for category '{}'.".format(len(element_ids), category_name_payload))
            return {
                "status": "success", 
                "message": "{} elements found for category '{}'.".format(len(element_ids), category_name_payload), 
                "count": len(element_ids),
                "category": category_name_payload,
                "element_ids": element_ids
            }

        except Exception as e_main_logic:
            route_logger.critical("Critical error in /get_elements_by_category: {}".format(e_main_logic), exc_info=True)
            return routes.Response(status=500, data={"error": "Internal server error during main logic.", "details": str(e_main_logic)})

    # Note: Additional element routes will be added here as the refactoring continues
    # This includes: select_elements_by_id, select_elements_simple, elements/filter, 
    # elements/get_properties, elements/update_parameters, etc. 