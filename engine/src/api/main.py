# engine/src/api/main.py

import os
import sys
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import fitz
import pytesseract
from PIL import Image

from engine.src.editor.editor_session import EditorSession
from engine.src.services.page_service import PageService
from engine.src.services.document_service import DocumentService
from engine.src.services.annotation_service import AnnotationService
from engine.src.plugin_system.plugin_manager import PluginManager
from engine.src.plugins.ocr_plugin import OCRPlugin
from engine.src.plugins.tts_plugin import TTSPlugin
from engine.src.plugins.redact_plugin import RedactPlugin

# Calculate the root directory of the project relative to this file
# main.py is in engine/src/api/
# 3 directories up gets us to the project root
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "..", "..", ".."))

if sys.platform == "win32":
    tesseract_path = os.path.join(project_root, "pytesseract", "tesseract.exe")
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

app = FastAPI(title="PDF Editor Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://127.0.0.1:5173",
        "https://pdfeditor-h8c5dzjdl-vince-ings-projects.vercel.app/", # Replace this string with your actual Vercel URL once generated
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Session registry ──────────────────────────────────────────────────────────

from fastapi import Depends, Header

sessions: dict[str, EditorSession] = {}

def get_session(session_id: str = Header(default="default", alias="X-Session-Id")) -> EditorSession:
    if session_id not in sessions:
        sessions[session_id] = EditorSession()
    return sessions[session_id]

# Initialise plugin_manager with a stable default session instance
_default_session = get_session("default")

plugin_manager = PluginManager(app, _default_session)
plugin_manager.register_plugin(OCRPlugin)
plugin_manager.register_plugin(TTSPlugin)
plugin_manager.register_plugin(RedactPlugin)
# NOTE: plugin_manager.finalize() intentionally not called — plugins use a
# hardcoded session and would ignore per-request X-Session-Id headers.
# Session-aware endpoints are defined directly below instead.

@app.delete("/api/session")
def close_session(
    session_id: str = Header(default="default", alias="X-Session-Id"),
):
    sessions.pop(session_id, None)
    return {"status": "success", "message": f"Session '{session_id}' closed."}


# ── Pydantic models ───────────────────────────────────────────────────────────

class CropPayload(BaseModel):
    x: float
    y: float
    width: float
    height: float

class MovePagePayload(BaseModel):
    new_index: int

class RotatePayload(BaseModel):
    degrees: int = 90

class LoadPayload(BaseModel):
    file_path: str

class ExportPayload(BaseModel):
    output_path: str

class TextRunPayload(BaseModel):
    text:        str
    bold:        bool  = False
    italic:      bool  = False
    font_family: str   = "Helvetica"
    font_size:   float = 12.0
    color:       str   = "#000000"

class TextAnnotationPayload(BaseModel):
    page_id:     str
    text:        str        = ""
    x:           float
    y:           float
    width:       float      = 200
    height:      float      = 30
    font_family: str        = "Helvetica"
    font_size:   float      = 12.0
    color:       str        = "#000000"
    bold:        bool       = False
    italic:      bool       = False
    runs:        List[TextRunPayload] = []

class UpdateAnnotationPayload(BaseModel):
    page_id:      str
    x:            Optional[float]              = None
    y:            Optional[float]              = None
    width:        Optional[float]              = None
    height:       Optional[float]              = None
    text_content: Optional[str]                = None
    font_family:  Optional[str]                = None
    font_size:    Optional[float]              = None
    color:        Optional[str]                = None
    bold:         Optional[bool]               = None
    italic:       Optional[bool]               = None
    runs:         Optional[List[TextRunPayload]] = None

class HighlightRect(BaseModel):
    x: float
    y: float
    width: float
    height: float

class HighlightPayload(BaseModel):
    page_id: str
    rects:   List[HighlightRect]
    color:   str   = "#FFFF00"
    opacity: float = 0.4

class PointPayload(BaseModel):
    x: float
    y: float

class PathAnnotationPayload(BaseModel):
    page_id:   str
    points:    List[PointPayload]
    color:     str   = "#000000"
    thickness: float = 2.0
    opacity:   float = 1.0

# ── Document endpoints ────────────────────────────────────────────────────────

@app.post("/api/document/upload")
def upload_and_load_document(file: UploadFile = File(...), session: EditorSession = Depends(get_session)):
    import shutil, traceback, tempfile, os
    print(f"--- Uploading: {file.filename} ---")
    try:
        # Get the system's universal temporary directory (works on Windows, Mac, and Linux)
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, file.filename)
        
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        service = DocumentService(session)
        doc_node = service.load_document(temp_path)
        return {"status": "success", "document": doc_node}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/document")
def get_document_state(session: EditorSession = Depends(get_session)):
    def node_to_dict(node):
        d = node.model_dump()
        d['children'] = [node_to_dict(c) for c in node.children]
        return d
    return node_to_dict(session.document)

@app.post("/api/document/load")
def load_document(payload: LoadPayload, session: EditorSession = Depends(get_session)):
    service = DocumentService(session)
    try:
        doc_node = service.load_document(payload.file_path)
        return {"status": "success", "document": doc_node}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.post("/api/document/export")
def export_document(payload: ExportPayload, session: EditorSession = Depends(get_session)):
    service = DocumentService(session)
    try:
        saved_path = service.export_document(payload.output_path)
        return {"status": "success", "file_saved": saved_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/document/download")
def download_document(session: EditorSession = Depends(get_session)):
    from fastapi.responses import Response
    if not session.document or not session.document.file_name:
        raise HTTPException(status_code=400, detail="No document loaded.")
    try:
        service = DocumentService(session)
        pdf_bytes = service.export_to_bytes()
        filename      = session.document.file_name
        download_name = f"edited_{filename}"
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Page endpoints ────────────────────────────────────────────────────────────

@app.post("/api/pages/{page_id}/crop")
def crop_page(page_id: str, payload: CropPayload, session: EditorSession = Depends(get_session)):
    try:
        service = PageService(session)
        service.crop_page(page_id, payload.x, payload.y, payload.width, payload.height)
        return {"status": "success", "message": "Page cropped."}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pages")
def create_page(page_number: int, source_ref: str = None, session: EditorSession = Depends(get_session)):
    service = PageService(session)
    return service.add_page(page_number, source_ref)

@app.post("/api/pages/{page_id}/rotate")
def rotate_page(page_id: str, payload: RotatePayload, session: EditorSession = Depends(get_session)):
    service = PageService(session)
    try:
        updated_page = service.rotate_page(page_id, payload.degrees)
        return {"status": "success", "page": updated_page.model_dump()}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@app.delete("/api/pages/{page_id}")
def delete_page(page_id: str, session: EditorSession = Depends(get_session)):
    try:
        before     = len(session.document.children)
        before_ids = [c.id for c in session.document.children]
        print(f"[DELETE] page_id={page_id}, before={before}, ids={before_ids}")
        service = PageService(session)
        service.delete_page(page_id)
        after     = len(session.document.children)
        after_ids = [c.id for c in session.document.children]
        print(f"[DELETE] after={after}, ids={after_ids}")
        return {"status": "success", "message": "Page deleted.", "before": before, "after": after}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/pages/{page_id}/move")
def move_page(page_id: str, payload: MovePagePayload, session: EditorSession = Depends(get_session)):
    try:
        service = PageService(session)
        service.move_page(page_id, payload.new_index)
        return {"status": "success", "message": "Page moved."}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pages/{page_id}/chars")
def get_page_chars(page_id: str, session: EditorSession = Depends(get_session)):
    service = PageService(session)
    try:
        chars = service.get_page_chars(page_id)
        return {"status": "success", "chars": chars}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Annotation endpoints ──────────────────────────────────────────────────────

@app.patch("/api/annotations/{node_id}")
def update_annotation(node_id: str, payload: UpdateAnnotationPayload, session: EditorSession = Depends(get_session)):
    service = AnnotationService(session)
    updates = payload.model_dump(exclude_unset=True)
    page_id = updates.pop("page_id", None)
    if not page_id:
        raise HTTPException(status_code=400, detail="page_id is required")
    try:
        node = service.update_annotation(page_id, node_id, updates)
        return {"status": "success", "node": node}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/annotations/text")
def add_text_annotation(payload: TextAnnotationPayload, session: EditorSession = Depends(get_session)):
    page = session.document.get_child(payload.page_id)
    if not page or page.node_type != "page":
        raise HTTPException(status_code=404, detail="Page not found")
    service = AnnotationService(session)
    runs_data = [r.model_dump() for r in payload.runs]
    node = service.add_text(
        page_id=payload.page_id,
        text=payload.text,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        font_family=payload.font_family,
        font_size=payload.font_size,
        color=payload.color,
        bold=payload.bold,
        italic=payload.italic,
        runs=runs_data,
    )
    return {"status": "success", "node": node}

@app.post("/api/annotations/highlight")
def add_highlight_annotation(payload: HighlightPayload, session: EditorSession = Depends(get_session)):
    page = session.document.get_child(payload.page_id)
    if not page or page.node_type != "page":
        raise HTTPException(status_code=404, detail="Page not found")
    service = AnnotationService(session)
    rect_dicts = [{"x": r.x, "y": r.y, "width": r.width, "height": r.height} for r in payload.rects]
    nodes = service.add_highlights(
        page_id=payload.page_id,
        rects=rect_dicts,
        color=payload.color,
        opacity=payload.opacity,
    )
    return {"status": "success", "nodes": nodes}

@app.post("/api/annotations/path")
def add_path_annotation(payload: PathAnnotationPayload, session: EditorSession = Depends(get_session)):
    page = session.document.get_child(payload.page_id)
    if not page or page.node_type != "page":
        raise HTTPException(status_code=404, detail="Page not found")
        
    service = AnnotationService(session)
    points_data = [{"x": p.x, "y": p.y} for p in payload.points]
    
    node = service.add_path(
        page_id=payload.page_id,
        points=points_data,
        color=payload.color,
        thickness=payload.thickness,
        opacity=payload.opacity
    )
    return {"status": "success", "node": node}

@app.delete("/api/annotations/{node_id}")
def delete_annotation(node_id: str, page_id: str, session: EditorSession = Depends(get_session)):
    service = AnnotationService(session)
    try:
        service.delete_annotation(node_id)
        return {"status": "success", "message": "Annotation deleted."}
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ── Plugin endpoints (session-aware) ─────────────────────────────────────────
#
# Plugins are not finalized via PluginManager because it binds a single session
# at startup and ignores per-request X-Session-Id headers. These endpoints
# replicate plugin logic with proper Depends(get_session) wiring.

class OCRPayload(BaseModel):
    page_id: str
    language: str = "eng"

@app.post("/api/plugins/ocr/process")
def run_ocr(payload: OCRPayload, session: EditorSession = Depends(get_session)):
    page = session.document.get_child(payload.page_id)
    if not page or page.node_type != "page":
        raise HTTPException(status_code=404, detail="Page not found")

    doc_path = session.document.file_path
    if not doc_path or not os.path.exists(doc_path):
        raise HTTPException(status_code=400, detail="Document file path is missing or invalid.")

    try:
        # Open the PDF using PyMuPDF
        pdf_doc = fitz.open(doc_path)
        
        # fitz is 0-indexed. Assuming page.page_number is 1-indexed
        fitz_page_num = max(0, page.page_number - 1)
        if fitz_page_num >= len(pdf_doc):
            raise HTTPException(status_code=400, detail="Invalid page number")
        
        pdf_page = pdf_doc[fitz_page_num]
        page_height = pdf_page.rect.height
        
        # Render page to an image at standard 72 DPI to match PDF coordinate space
        pix = pdf_page.get_pixmap(matrix=fitz.Matrix(1, 1))
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

        # Execute OCR and extract data
        ocr_data = pytesseract.image_to_data(
            img, 
            lang=payload.language, 
            output_type=pytesseract.Output.DICT
        )

        annot_service = AnnotationService(session)
        added_nodes = []
        n_boxes = len(ocr_data['text'])

        # Mutate the Scene Graph using the standardized service layer
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            if text:  # Ignore empty strings or whitespace-only detections
                w = ocr_data['width'][i]
                h = ocr_data['height'][i]
                x = ocr_data['left'][i]
                y_tesseract = ocr_data['top'][i]
                
                # Invert the Y-axis to match the PDF coordinate system (origin at bottom-left)
                y_pdf = page_height - (y_tesseract + h)

                node = annot_service.add_text(
                    page_id=payload.page_id,
                    text=text,
                    x=x,
                    y=y_pdf,
                    width=w,
                    height=h
                )
                added_nodes.append(node)

        pdf_doc.close()

        return {
            "status": "success",
            "message": f"OCR complete. Added {len(added_nodes)} text nodes.",
            "nodes": added_nodes
        }

    except pytesseract.pytesseract.TesseractNotFoundError:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500, 
            detail=f"Tesseract executable not found at {tesseract_path}. Please ensure it exists."
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")


# ── Undo / Redo ───────────────────────────────────────────────────────────────

@app.post("/api/undo")
def undo_last_action(session: EditorSession = Depends(get_session)):
    if not session.undo():
        raise HTTPException(status_code=400, detail="Nothing to undo.")
    return {"status": "success", "message": "Undo successful."}

@app.post("/api/redo")
def redo_last_action(session: EditorSession = Depends(get_session)):
    if not session.redo():
        raise HTTPException(status_code=400, detail="Nothing to redo.")
    return {"status": "success", "message": "Redo successful."}