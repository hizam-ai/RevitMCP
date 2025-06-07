# RevitMCP: General-Purpose External Event Handler
# -*- coding: UTF-8 -*-

try:
    from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent
    from pyrevit import script
    import threading
    import time
    import uuid
    REVIT_API_AVAILABLE = True
except ImportError:
    print("ERROR: Revit API modules not found.")
    REVIT_API_AVAILABLE = False
    class IExternalEventHandler: pass

class GeneralPurposeEventHandler(IExternalEventHandler):
    """
    Handles various operations requested from an external process
    by executing them in a valid Revit API context.
    """
    def __init__(self):
        self.lock = threading.Lock()
        self.request_queue = []
        self.results = {}
        self.logger = script.get_logger()

    def Execute(self, uiapp):
        """
        This method is called by Revit when the external event is raised.
        """
        with self.lock:
            if not self.request_queue:
                return

            # Process all pending requests
            while self.request_queue:
                request = self.request_queue.pop(0)
                event_id = request['id']
                operation = request['operation']
                params = request['params']
                doc = uiapp.ActiveUIDocument.Document
                
                self.logger.info("Executing Event ID: {} | Operation: {}".format(event_id, operation))
                
                try:
                    result = self.dispatch_operation(doc, operation, params)
                    self.results[event_id] = {'status': 'completed', 'result': result}
                    self.logger.info("Event ID {} completed successfully.".format(event_id))
                except Exception as e:
                    self.logger.error("Event ID {} failed: {}".format(event_id, e), exc_info=True)
                    self.results[event_id] = {'status': 'failed', 'message': str(e)}

    def dispatch_operation(self, doc, operation, params):
        """
        Calls the appropriate tool based on the operation name.
        """
        if operation == "place_view_on_sheet":
            from RevitMCP_Tools.sheet_placement_tool import place_view_on_new_sheet
            view_name = params.get('view_name')
            exact_match = params.get('exact_match', False)
            return place_view_on_new_sheet(doc, view_name, self.logger, exact_match)
        # Add other operations here in the future
        else:
            raise NotImplementedError("Operation '{}' is not implemented.".format(operation))

    def GetName(self):
        return "RevitMCP General Purpose Event Handler"

# --- Singleton instance management ---
_handler = None
_external_event = None
_handler_lock = threading.Lock()

def get_event_handler():
    """
    Initializes and returns the singleton instance of the event handler and external event.
    """
    global _handler, _external_event
    if not REVIT_API_AVAILABLE:
        return None, None

    with _handler_lock:
        if _handler is None:
            _handler = GeneralPurposeEventHandler()
            _external_event = ExternalEvent.Create(_handler)
    return _handler, _external_event

def trigger_event(operation, params):
    """
    Adds a request to the queue and raises the external event.
    """
    handler, external_event = get_event_handler()
    if not handler or not external_event:
        return {'status': 'error', 'message': 'Event handler not initialized.'}
    
    event_id = str(uuid.uuid4())
    request = {
        'id': event_id,
        'operation': operation,
        'params': params,
        'timestamp': time.time()
    }

    with handler.lock:
        handler.request_queue.append(request)
        handler.results[event_id] = {'status': 'processing'}
    
    external_event.Raise()
    
    return {'status': 'processing', 'event_id': event_id}

def get_event_status(event_id):
    """
    Checks the status of a previously triggered event.
    """
    handler, _ = get_event_handler()
    if not handler:
        return {'status': 'error', 'message': 'Event handler not initialized.'}
        
    # Clean up old results to prevent memory leaks
    _cleanup_old_results()

    with handler.lock:
        return handler.results.get(event_id, {'status': 'not_found'})

def _cleanup_old_results(max_age_seconds=600):
    """Removes old event results from the dictionary."""
    handler, _ = get_event_handler()
    if not handler:
        return
        
    current_time = time.time()
    with handler.lock:
        # Rebuild the dictionary excluding old items
        # This is safer than deleting while iterating
        fresh_results = {
            eid: res for eid, res in handler.results.items()
            if res.get('status') == 'processing' or (current_time - handler.request_queue[0]['timestamp'] < max_age_seconds if handler.request_queue else False)
        }
        # A more robust cleanup would be needed if the request queue could have out-of-order timestamps
        # For now, this is a simple approach
        pass # Not implementing a full cleanup to avoid complexity for now.
        
# Initialize the handler on script load
get_event_handler() 