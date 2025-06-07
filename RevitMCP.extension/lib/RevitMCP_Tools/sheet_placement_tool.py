# RevitMCP: This script runs in pyRevit (IronPython).
# -*- coding: UTF-8 -*-
"""
Sheet Placement Tool - handles creating sheets and placing views with viewports.
"""

try:
    import Autodesk
    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        FamilySymbol,
        ViewSheet,
        View,
        ViewFamily,
        ViewFamilyType,
        ViewType,
        BuiltInCategory,
        ElementId,
        Viewport,
        XYZ,
        BoundingBoxUV,
        UV,
        Transaction
    )
    from Autodesk.Revit.Creation import Application
    from Autodesk.Revit.UI import UIApplication
    # Import pyRevit DB for transaction handling
    from pyrevit import DB
    from pyrevit import revit, script
    import System
    REVIT_API_AVAILABLE = True
except ImportError:
    print("ERROR (sheet_placement_tool): Revit API modules not found. This script must run in Revit.")
    REVIT_API_AVAILABLE = False
    # Placeholder for non-Revit environments
    FilteredElementCollector = None
    FamilySymbol = None
    ViewSheet = None
    View = None
    ViewFamily = None
    ViewFamilyType = None
    ViewType = None
    BuiltInCategory = None
    ElementId = None
    Viewport = None
    XYZ = None
    BoundingBoxUV = None
    UV = None
    # Placeholder for DB
    class DB:
        class Transaction:
            def __init__(self, doc, name): pass
            def Start(self): pass
            def Commit(self): pass
            def RollBack(self): pass


def find_views_by_name(doc, view_name, logger, exact_match=False):
    """
    Find views by name with fuzzy matching capability.
    
    Args:
        doc: Revit Document
        view_name (str): Name of the view to search for
        logger: Logger instance
        exact_match (bool): Whether to require exact name match
    
    Returns:
        list: List of matching View objects
    """
    if not doc or not view_name:
        logger.error("SheetPlacementTool: Invalid document or view name provided")
        return []
    
    try:
        # Collect all views in the document
        views = FilteredElementCollector(doc).OfClass(View).ToElements()
        matching_views = []
        
        view_name_lower = view_name.lower().strip()
        
        for view in views:
            if not hasattr(view, 'Name') or not view.Name:
                continue
                
            view_name_actual = view.Name.strip()
            
            if exact_match:
                if view_name_actual.lower() == view_name_lower:
                    matching_views.append(view)
            else:
                # Fuzzy matching - check if search term is contained in view name
                if view_name_lower in view_name_actual.lower():
                    matching_views.append(view)
        
        logger.info("SheetPlacementTool: Found {} matching view(s) for '{}'".format(len(matching_views), view_name))
        return matching_views
        
    except Exception as e:
        logger.error("SheetPlacementTool: Error finding views: {}".format(e), exc_info=True)
        return []


def get_titleblock_family_symbols(doc, logger):
    """
    Get available titleblock family symbols for sheet creation.
    
    Args:
        doc: Revit Document
        logger: Logger instance
    
    Returns:
        list: List of FamilySymbol objects that are titleblocks
    """
    try:
        # Collect all titleblock family symbols
        titleblocks = FilteredElementCollector(doc)\
            .OfCategory(BuiltInCategory.OST_TitleBlocks)\
            .OfClass(FamilySymbol)\
            .ToElements()
        
        # Filter to only active/loaded symbols
        active_titleblocks = [tb for tb in titleblocks if tb.IsActive]
        
        logger.info("SheetPlacementTool: Found {} active titleblock family symbols".format(len(active_titleblocks)))
        return active_titleblocks
        
    except Exception as e:
        logger.error("SheetPlacementTool: Error getting titleblocks: {}".format(e), exc_info=True)
        return []


def find_next_sheet_number(doc, view_type_name, logger):
    """
    Find the next available sheet number based on existing sheets of similar type.
    
    Args:
        doc: Revit Document
        view_type_name (str): Type of view to base numbering on (e.g., "Detail", "Section", "Plan")
        logger: Logger instance
    
    Returns:
        str: Next available sheet number
    """
    try:
        # Get all existing sheets
        sheets = FilteredElementCollector(doc).OfClass(ViewSheet).ToElements()
        
        # Extract sheet numbers and look for patterns
        sheet_numbers = []
        view_type_prefix = view_type_name.upper()[:1]  # D for Detail, S for Section, P for Plan, etc.
        
        for sheet in sheets:
            if hasattr(sheet, 'SheetNumber') and sheet.SheetNumber:
                sheet_num = sheet.SheetNumber.strip()
                sheet_numbers.append(sheet_num)
        
        logger.debug("SheetPlacementTool: Found {} existing sheets".format(len(sheet_numbers)))
        
        # Look for existing patterns with this view type prefix
        matching_numbers = []
        for num in sheet_numbers:
            if num.startswith(view_type_prefix):
                try:
                    # Extract numeric part after prefix
                    numeric_part = ''.join(filter(str.isdigit, num))
                    if numeric_part:
                        matching_numbers.append(int(numeric_part))
                except:
                    continue
        
        if matching_numbers:
            next_num = max(matching_numbers) + 1
            next_sheet_number = "{}{:03d}".format(view_type_prefix, next_num)
        else:
            # No existing sheets of this type, start with 001
            next_sheet_number = "{}{:03d}".format(view_type_prefix, 1)
        
        logger.info("SheetPlacementTool: Next sheet number: {}".format(next_sheet_number))
        return next_sheet_number
        
    except Exception as e:
        logger.error("SheetPlacementTool: Error finding next sheet number: {}".format(e), exc_info=True)
        return "S001"  # Fallback


def create_new_sheet(doc, sheet_number, sheet_name, titleblock_symbol, logger):
    """
    Create a new sheet with the specified parameters.
    
    Args:
        doc: Revit Document
        sheet_number (str): Sheet number
        sheet_name (str): Sheet name
        titleblock_symbol: FamilySymbol for titleblock
        logger: Logger instance
    
    Returns:
        ViewSheet: Created sheet or None if failed
    """
    try:
        # Create the sheet
        new_sheet = ViewSheet.Create(doc, titleblock_symbol.Id)
        
        if new_sheet:
            # Set sheet number and name
            new_sheet.SheetNumber = sheet_number
            new_sheet.Name = sheet_name
            
            logger.info("SheetPlacementTool: Created sheet '{}' - '{}'".format(sheet_number, sheet_name))
            return new_sheet
        else:
            logger.error("SheetPlacementTool: Failed to create sheet")
            return None
            
    except Exception as e:
        logger.error("SheetPlacementTool: Error creating sheet: {}".format(e), exc_info=True)
        return None


def get_sheet_center_point(sheet, logger):
    """
    Calculate the center point of a sheet for viewport placement.
    
    Args:
        sheet: ViewSheet object
        logger: Logger instance
    
    Returns:
        XYZ: Center point coordinates
    """
    try:
        # Get the sheet's outline
        outline = sheet.Outline
        if outline:
            min_point = outline.Min
            max_point = outline.Max
            
            # Calculate center
            center_x = (min_point.X + max_point.X) / 2.0
            center_y = (min_point.Y + max_point.Y) / 2.0
            center_point = XYZ(center_x, center_y, 0.0)
            
            logger.debug("SheetPlacementTool: Sheet center point: ({}, {})".format(center_x, center_y))
            return center_point
        else:
            # Fallback to a typical sheet center
            center_point = XYZ(0.5, 0.5, 0.0)
            logger.warning("SheetPlacementTool: Could not get sheet outline, using fallback center point")
            return center_point
            
    except Exception as e:
        logger.error("SheetPlacementTool: Error calculating sheet center: {}".format(e), exc_info=True)
        # Fallback center point
        return XYZ(0.5, 0.5, 0.0)


def place_view_on_sheet(doc, view, sheet, location_point, logger):
    """
    Place a view on a sheet as a viewport.
    
    Args:
        doc: Revit Document
        view: View to place
        sheet: ViewSheet to place view on
        location_point: XYZ point for viewport location
        logger: Logger instance
    
    Returns:
        Viewport: Created viewport or None if failed
    """
    try:
        # Check if view can be placed on a sheet
        if not view.CanBePrinted:
            logger.warning("SheetPlacementTool: View '{}' cannot be printed, may not be suitable for sheets".format(view.Name))
        
        # Check if view is already on a sheet
        if hasattr(view, 'Sheet') and view.Sheet and view.Sheet.Id != ElementId.InvalidElementId:
            logger.warning("SheetPlacementTool: View '{}' is already placed on sheet '{}'".format(view.Name, view.Sheet.Name))
            return None
        
        # Create the viewport
        viewport = Viewport.Create(doc, sheet.Id, view.Id, location_point)
        
        if viewport:
            logger.info("SheetPlacementTool: Successfully placed view '{}' on sheet '{}'".format(view.Name, sheet.Name))
            return viewport
        else:
            logger.error("SheetPlacementTool: Failed to create viewport")
            return None
            
    except Exception as e:
        logger.error("SheetPlacementTool: Error placing view on sheet: {}".format(e), exc_info=True)
        return None


def get_view_type_name(view, logger):
    """
    Get a human-readable name for the view type.
    
    Args:
        view: View object
        logger: Logger instance
    
    Returns:
        str: View type name
    """
    try:
        if hasattr(view, 'ViewType'):
            view_type = view.ViewType
            
            # Map common view types to readable names
            type_mapping = {
                ViewType.Detail: "Detail",
                ViewType.Section: "Section",
                ViewType.Elevation: "Elevation",
                ViewType.FloorPlan: "Plan",
                ViewType.CeilingPlan: "Ceiling Plan",
                ViewType.ThreeD: "3D View",
                ViewType.Schedule: "Schedule",
                ViewType.DrawingSheet: "Sheet",
                ViewType.Report: "Report",
                ViewType.DraftingView: "Drafting",
                ViewType.Legend: "Legend",
                ViewType.EngineeringPlan: "Engineering Plan",
                ViewType.AreaPlan: "Area Plan"
            }
            
            return type_mapping.get(view_type, str(view_type))
        else:
            return "Unknown"
            
    except Exception as e:
        logger.error("SheetPlacementTool: Error getting view type: {}".format(e), exc_info=True)
        return "Unknown"


def place_view_on_new_sheet(doc, view_name, logger, exact_match=False):
    """
    Create a new sheet and place the specified view on it.
    This version uses standard Revit API Transaction for external event context.
    """
    if not REVIT_API_AVAILABLE:
        return {"status": "error", "message": "Revit API not available"}
    
    try:
        logger.info("Starting sheet creation for view: '{}'".format(view_name))
        
        # Find the view
        all_views = FilteredElementCollector(doc).OfClass(View).WhereElementIsNotElementType().ToElements()
        target_view = None
        
        for view in all_views:
            if hasattr(view, 'Name') and view.Name:
                if exact_match:
                    if view.Name == view_name:
                        target_view = view
                        break
                else:
                    if view_name.lower() in view.Name.lower():
                        target_view = view
                        break
        
        if not target_view:
            logger.error("View '{}' not found".format(view_name))
            return {"status": "error", "message": "View '{}' not found".format(view_name)}
        
        logger.info("Found view: '{}' (ID: {})".format(target_view.Name, target_view.Id))
        
        # Check if view can be placed on sheet
        if not hasattr(target_view, 'CanBePlacedOnSheet') or not target_view.CanBePlacedOnSheet:
            logger.error("View '{}' cannot be placed on sheet".format(view_name))
            return {"status": "error", "message": "View '{}' cannot be placed on sheet".format(view_name)}
        
        # Find a titleblock family symbol
        titleblocks = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_TitleBlocks).WhereElementIsElementType().ToElements()
        
        if not titleblocks:
            logger.error("No titleblock family found in project")
            return {"status": "error", "message": "No titleblock family found in project"}
        
        titleblock = titleblocks[0]
        logger.info("Using titleblock: '{}'".format(titleblock.Name))
        
        # Use standard Revit API Transaction (we're in external event context)
        t = Transaction(doc, "Create Sheet and Place View")
        
        try:
            logger.info("Starting transaction...")
            t.Start()
            
            # Create the sheet
            new_sheet = ViewSheet.Create(doc, titleblock.Id)
            logger.info("Created sheet with ID: {}".format(new_sheet.Id))
            
            # Set sheet name and number
            sheet_number = "S-{:03d}".format(new_sheet.Id.IntegerValue % 1000)
            sheet_name = "Sheet for {}".format(target_view.Name)
            
            new_sheet.SheetNumber = sheet_number
            new_sheet.Name = sheet_name
            
            logger.info("Set sheet number: '{}', name: '{}'".format(sheet_number, sheet_name))
            
            # Place the view on the sheet at center
            sheet_center = XYZ(0, 0, 0)  # This will be adjusted by Revit automatically
            
            logger.info("Placing view on sheet...")
            viewport = Viewport.Create(doc, new_sheet.Id, target_view.Id, sheet_center)
            
            logger.info("View placed successfully. Viewport ID: {}".format(viewport.Id))
            
            # Commit the transaction
            logger.info("Committing transaction...")
            t.Commit()
            
            logger.info("Sheet creation completed successfully!")
            
            return {
                "status": "success",
                "message": "Successfully created sheet '{}' with view '{}'".format(sheet_number, target_view.Name),
                "sheet_id": str(new_sheet.Id),
                "sheet_number": sheet_number,
                "sheet_name": sheet_name,
                "view_name": target_view.Name,
                "viewport_id": str(viewport.Id)
            }
            
        except Exception as e:
            logger.error("Transaction error: {}".format(e), exc_info=True)
            if t.HasStarted():
                t.RollBack()
                logger.info("Transaction rolled back")
            
            return {
                "status": "error",
                "message": "Failed to create sheet: {}".format(str(e)),
                "view_name": view_name
            }
            
    except Exception as e:
        logger.error("Sheet creation error: {}".format(e), exc_info=True)
        return {
            "status": "error",
            "message": "Unexpected error: {}".format(str(e)),
            "view_name": view_name
        } 