from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from engine.src.plugin_system.plugin import Plugin
from engine.src.editor.editor_session import EditorSession
from engine.src.services.annotation_service import AnnotationService

# Assuming your existing redact command/service handles the PyMuPDF physical redaction
from engine.src.services.redaction_service import RedactionService

class BoundingBoxPayload(BaseModel):
    x: float
    y: float
    width: float
    height: float

class RedactRequest(BaseModel):
    page_id: str
    rects: List[BoundingBoxPayload]

class RedactPlugin(Plugin):
    @property
    def name(self) -> str:
        return "Redact"

    @property
    def version(self) -> str:
        return "1.0.0"

    def register_routes(self, router: APIRouter, session: EditorSession) -> None:
        
        @router.post("/apply")
        def apply_redaction(payload: RedactRequest):
            """
            Applies redaction boxes to a page. 
            In the Scene Graph, we represent these as black HighlightNodes 100% opaque.
            The actual physical redaction will happen during DocumentService.export_document.
            """
            page = session.document.get_child(payload.page_id)
            if not page or page.node_type != "page":
                raise HTTPException(status_code=404, detail="Page not found")

            annot_service = AnnotationService(session)
            added_nodes = []

            for rect in payload.rects:
                # Add an opaque black rectangle to the scene graph
                node = annot_service.add_highlight(
                    page_id=payload.page_id,
                    x=rect.x,
                    y=rect.y,
                    width=rect.width,
                    height=rect.height,
                    color="#000000" # Black
                )
                # Override the default 0.5 opacity for a redaction
                node.opacity = 1.0 
                added_nodes.append(node)

            return {
                "status": "success",
                "message": f"Applied {len(added_nodes)} redaction zones.",
                "nodes": added_nodes
            }