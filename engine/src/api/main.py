import os
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from engine.src.editor.editor_session import EditorSession
from engine.src.services.page_service import PageService
from engine.src.services.document_service import DocumentService
from engine.src.services.annotation_service import AnnotationService
from engine.src.plugin_system.plugin_manager import PluginManager
from engine.src.plugins.ocr_plugin import OCRPlugin
from engine.src.plugins.tts_plugin import TTSPlugin
from engine.src.plugins.redact_plugin import RedactPlugin

app = FastAPI(title="PDF Editor Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

current_session = EditorSession()

plugin_manager = PluginManager(app, current_session)
plugin_manager.register_plugin(OCRPlugin)
plugin_manager.register_plugin(TTSPlugin)
plugin_manager.register_plugin(RedactPlugin)
plugin_manager.finalize()


# ── Pydantic models ───────────────────────────────────────────────────────────

class MovePagePayload(BaseModel):
    new_index: int

class RotatePayload(BaseModel):
    degrees: int = 90

class LoadPayload(BaseModel):
    file_path: str

class ExportPayload(BaseModel):
    output_path: str

class TextAnnotationPayload(BaseModel):
    page_id: str
    text: str
    x: float
    y: float
    width: float = 200
    height: float = 30
    font_size: float = 12.0
    color: str = "#000000"

class HighlightPayload(BaseModel):
    page_id: str
    x: float
    y: float
    width: float
    height: float
    color: str = "#FFFF00"
    opacity: float = 0.4


# ── Document endpoints ────────────────────────────────────────────────────────

@app.post("/api/document/upload")
def upload_and_load_document(file: UploadFile = File(...)):
    import shutil, traceback
    print(f"--- Uploading: {file.filename} ---")
    try:
        os.makedirs(".workspace", exist_ok=True)
        temp_path = f".workspace/{file.filename}"
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        service = DocumentService(current_session)
        doc_node = service.load_document(temp_path)
        return {"status": "success", "document": doc_node}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/document")
def get_document_state():
    def node_to_dict(node):
        d = node.model_dump()
        d['children'] = [node_to_dict(c) for c in node.children]
        return d
    return node_to_dict(current_session.document)

@app.post("/api/document/load")
def load_document(payload: LoadPayload):
    service = DocumentService(current_session)
    try:
        doc_node = service.load_document(payload.file_path)
        return {"status": "success", "document": doc_node}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/document/export")
def export_document(payload: ExportPayload):
    service = DocumentService(current_session)
    try:
        saved_path = service.export_document(payload.output_path)
        return {"status": "success", "file_saved": saved_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/document/download")
def download_document():
    """Stream the modified PDF directly to the browser as a file download."""
    from fastapi.responses import Response
    if not current_session.document or not current_session.document.file_name:
        raise HTTPException(status_code=400, detail="No document loaded.")
    try:
        service = DocumentService(current_session)
        pdf_bytes = service.export_to_bytes()
        filename = current_session.document.file_name
        download_name = f"edited_{filename}"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'}
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Page endpoints ────────────────────────────────────────────────────────────

@app.post("/api/pages")
def create_page(page_number: int, source_ref: str = None):
    service = PageService(current_session)
    return service.add_page(page_number, source_ref)

@app.post("/api/pages/{page_id}/rotate")
def rotate_page(page_id: str, payload: RotatePayload):
    service = PageService(current_session)
    try:
        updated_page = service.rotate_page(page_id, payload.degrees)
        return {"status": "success", "page": updated_page.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/api/pages/{page_id}")
def delete_page(page_id: str):
    try:
        before = len(current_session.document.children)
        before_ids = [c.id for c in current_session.document.children]
        print(f"[DELETE] page_id={page_id}")
        print(f"[DELETE] before count={before}, ids={before_ids}")

        service = PageService(current_session)
        service.delete_page(page_id)

        after = len(current_session.document.children)
        after_ids = [c.id for c in current_session.document.children]
        print(f"[DELETE] after count={after}, ids={after_ids}")

        return {
            "status": "success",
            "message": "Page deleted.",
            "before": before,
            "after": after,
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pages/{page_id}/move")
def move_page(page_id: str, payload: MovePagePayload):
    try:
        before_ids = [c.id for c in current_session.document.children]
        print(f"[MOVE] page_id={page_id} new_index={payload.new_index}")
        print(f"[MOVE] before ids={before_ids}")

        service = PageService(current_session)
        service.move_page(page_id, payload.new_index)

        after_ids = [c.id for c in current_session.document.children]
        print(f"[MOVE] after ids={after_ids}")

        return {"status": "success", "message": "Page moved."}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pages/{page_id}/chars")
def get_page_chars(page_id: str):
    service = PageService(current_session)
    try:
        chars = service.get_page_chars(page_id)
        return {"status": "success", "chars": chars}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Annotation endpoints ──────────────────────────────────────────────────────

@app.post("/api/annotations/text")
def add_text_annotation(payload: TextAnnotationPayload):
    page = current_session.document.get_child(payload.page_id)
    if not page or page.node_type != "page":
        raise HTTPException(status_code=404, detail="Page not found")
    service = AnnotationService(current_session)
    node = service.add_text(
        page_id=payload.page_id,
        text=payload.text,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        font_size=payload.font_size,
        color=payload.color,
    )
    return {"status": "success", "node": node}

@app.post("/api/annotations/highlight")
def add_highlight_annotation(payload: HighlightPayload):
    page = current_session.document.get_child(payload.page_id)
    if not page or page.node_type != "page":
        raise HTTPException(status_code=404, detail="Page not found")
    service = AnnotationService(current_session)
    node = service.add_highlight(
        page_id=payload.page_id,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        color=payload.color,
    )
    node.opacity = payload.opacity
    return {"status": "success", "node": node}


# ── Undo / Redo ───────────────────────────────────────────────────────────────

@app.post("/api/undo")
def undo_last_action():
    if not current_session.undo():
        raise HTTPException(status_code=400, detail="Nothing to undo.")
    return {"status": "success", "message": "Undo successful."}

@app.post("/api/redo")
def redo_last_action():
    if not current_session.redo():
        raise HTTPException(status_code=400, detail="Nothing to redo.")
    return {"status": "success", "message": "Redo successful."}