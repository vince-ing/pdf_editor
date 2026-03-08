# engine/src/plugins/redact_plugin.py

from typing import List
from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from engine.src.plugin_system.plugin import Plugin
from engine.src.editor.editor_session import EditorSession
from engine.src.services.annotation_service import AnnotationService

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

            # Use batch add_highlights to group undo operations into one command
            rect_dicts = [{"x": r.x, "y": r.y, "width": r.width, "height": r.height} for r in payload.rects]
            
            added_nodes = annot_service.add_highlights(
                page_id=payload.page_id,
                rects=rect_dicts,
                color="#000000",
                opacity=1.0
            )

            return {
                "status": "success",
                "message": f"Applied {len(added_nodes)} redaction zones.",
                "nodes": added_nodes
            }