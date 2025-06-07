# RevitMCP: Simple test for sheet creation
# -*- coding: UTF-8 -*-

try:
    from Autodesk.Revit.DB import (
        FilteredElementCollector,
        FamilySymbol,
        ViewSheet,
        BuiltInCategory
    )
    from pyrevit import DB
    REVIT_API_AVAILABLE = True
except ImportError:
    print("ERROR: Revit API modules not found.")
    REVIT_API_AVAILABLE = False

def test_simple_sheet_creation(doc, logger):
    """
    Simple test to create a sheet with transaction to isolate the issue.
    """
    if not REVIT_API_AVAILABLE:
        return {"status": "error", "message": "Revit API not available"}
    
    try:
        logger.info("Starting simple sheet creation test")
        
        # Get available titleblocks
        titleblocks = FilteredElementCollector(doc)\
            .OfCategory(BuiltInCategory.OST_TitleBlocks)\
            .OfClass(FamilySymbol)\
            .ToElements()
        
        active_titleblocks = [tb for tb in titleblocks if tb.IsActive]
        
        if not active_titleblocks:
            return {"status": "error", "message": "No active titleblocks found"}
        
        titleblock = active_titleblocks[0]
        logger.info("Using titleblock: {}".format(titleblock.Family.Name))
        
        # Try creating sheet with transaction using explicit pattern
        t = DB.Transaction(doc, "Test Simple Sheet Creation")
        t.Start()
        
        try:
            # Create the sheet
            new_sheet = ViewSheet.Create(doc, titleblock.Id)
            
            if new_sheet:
                new_sheet.SheetNumber = "TEST001"
                new_sheet.Name = "Test Sheet"
                
                t.Commit()
                logger.info("Successfully created test sheet: {}".format(new_sheet.SheetNumber))
                
                return {
                    "status": "success",
                    "message": "Successfully created test sheet",
                    "sheet_number": new_sheet.SheetNumber,
                    "sheet_id": str(new_sheet.Id.IntegerValue)
                }
            else:
                t.RollBack()
                return {"status": "error", "message": "Failed to create sheet"}
                
        except Exception as inner_error:
            t.RollBack()
            logger.error("Inner transaction error: {}".format(inner_error), exc_info=True)
            return {
                "status": "error", 
                "message": "Inner transaction failed: {}".format(str(inner_error))
            }
    
    except Exception as e:
        logger.error("Test sheet creation failed: {}".format(e), exc_info=True)
        return {
            "status": "error",
            "message": "Test failed: {}".format(str(e))
        } 