from pydantic import BaseModel
from fastapi import APIRouter, HTTPException
from engine.src.plugin_system.plugin import Plugin
from engine.src.editor.editor_session import EditorSession
from engine.src.services.annotation_service import AnnotationService

class OCRRequest(BaseModel):
    page_id: str
    language: str = "eng"

class OCRPlugin(Plugin):
    @property
    def name(self) -> str:
        return "OCR"

    @property
    def version(self) -> str:
        return "1.0.0"

    def register_routes(self, router: APIRouter, session: EditorSession) -> None:
        
        @router.post("/process")
        def process_ocr(payload: OCRRequest):
            """
            Executes OCR on a specific page and adds the detected text 
            to the Scene Graph as TextNodes.
            """
            page = session.document.get_child(payload.page_id)
            if not page or page.node_type != "page":
                raise HTTPException(status_code=404, detail="Page not found")

            # TODO: Import and call your existing Tesseract/pytesseract logic here
            # example_extracted_data = your_ocr_service.extract_text(page.source_reference)
            
            # Mock extracted data for demonstration
            extracted_blocks = [
                {"text": "Recognized Text 1", "x": 50, "y": 100, "w": 200, "h": 20},
                {"text": "Recognized Text 2", "x": 50, "y": 150, "w": 180, "h": 20}
            ]

            annot_service = AnnotationService(session)
            added_nodes = []

            # Mutate the Scene Graph using the standardized service layer
            for block in extracted_blocks:
                node = annot_service.add_text(
                    page_id=payload.page_id,
                    text=block["text"],
                    x=block["x"],
                    y=block["y"],
                    width=block["w"],
                    height=block["h"]
                )
                added_nodes.append(node)

            return {
                "status": "success",
                "message": f"OCR complete. Added {len(added_nodes)} text nodes.",
                "nodes": added_nodes
            }