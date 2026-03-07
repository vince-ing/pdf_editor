import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Core Engine Imports
from engine.src.editor.editor_session import EditorSession
from engine.src.services.page_service import PageService
from engine.src.services.document_service import DocumentService

# Plugin Imports
from engine.src.plugin_system.plugin_manager import PluginManager
from engine.src.plugins.ocr_plugin import OCRPlugin
from engine.src.plugins.tts_plugin import TTSPlugin
from engine.src.plugins.redact_plugin import RedactPlugin

app = FastAPI(title="PDF Editor Engine API")

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Session Management ---
# THIS must be defined before the PluginManager uses it!
current_session = EditorSession()

# --- Initialize Plugin System ---
plugin_manager = PluginManager(app, current_session)

# Register Plugins
plugin_manager.register_plugin(OCRPlugin)
plugin_manager.register_plugin(TTSPlugin)
plugin_manager.register_plugin(RedactPlugin)

# Finalize mounts the /api/plugins router to the main app
plugin_manager.finalize()


# --- Pydantic Payloads ---
class RotatePayload(BaseModel):
    degrees: int = 90

class LoadPayload(BaseModel):
    file_path: str

class ExportPayload(BaseModel):
    output_path: str


# --- Endpoints ---
@app.post("/api/document/upload")
def upload_and_load_document(file: UploadFile = File(...)):
    import shutil
    import traceback
    
    print(f"--- Attempting to upload: {file.filename} ---")
    try:
        os.makedirs(".workspace", exist_ok=True)
        temp_path = f".workspace/{file.filename}"
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"File saved to {temp_path}. Loading into engine...")
        
        service = DocumentService(current_session)
        doc_node = service.load_document(temp_path)
        
        print("Successfully loaded into engine!")
        return {"status": "success", "document": doc_node}
        
    except Exception as e:
        print("\n!!! UPLOAD FAILED !!!")
        traceback.print_exc() # This prints the exact line that crashed
        raise HTTPException(status_code=500, detail=str(e))
    
@app.get("/api/document")
def get_document_state():
    """Returns the entire Document Scene Graph."""
    return current_session.document

@app.post("/api/pages")
def create_page(page_number: int, source_ref: str = None):
    """Adds a new page to the document."""
    service = PageService(current_session)
    new_page = service.add_page(page_number, source_ref)
    return new_page

@app.post("/api/pages/{page_id}/rotate")
def rotate_page(page_id: str, payload: RotatePayload):
    """Rotates a specific page."""
    service = PageService(current_session)
    try:
        updated_page = service.rotate_page(page_id, payload.degrees)
        return {"status": "success", "page": updated_page}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/document/load")
def load_document(payload: LoadPayload):
    """Loads a physical PDF into the engine state."""
    service = DocumentService(current_session)
    try:
        doc_node = service.load_document(payload.file_path)
        return {"status": "success", "document": doc_node}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/document/export")
def export_document(payload: ExportPayload):
    """Saves the current engine state to a physical PDF."""
    service = DocumentService(current_session)
    try:
        saved_path = service.export_document(payload.output_path)
        return {"status": "success", "file_saved": saved_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/undo")
def undo_last_action():
    """Undoes the last command in the engine."""
    success = current_session.undo()
    if not success:
        raise HTTPException(status_code=400, detail="Nothing to undo.")
    return {"status": "success", "message": "Undo successful."}

@app.post("/api/redo")
def redo_last_action():
    """Redoes the last undone command."""
    success = current_session.redo()
    if not success:
        raise HTTPException(status_code=400, detail="Nothing to redo.")
    return {"status": "success", "message": "Redo successful."}