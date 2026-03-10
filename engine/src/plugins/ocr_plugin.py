import os
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
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
            to the Scene Graph as TextNodes using pytesseract.
            """
            page = session.document.get_child(payload.page_id)
            if not page or page.node_type != "page":
                raise HTTPException(status_code=404, detail="Page not found")

            doc_path = session.document.file_path
            if not doc_path or not os.path.exists(doc_path):
                raise HTTPException(status_code=400, detail="Document file path is missing or invalid.")

            try:
                # Open the PDF using PyMuPDF
                pdf_doc = fitz.open(doc_path)
                
                # fitz is 0-indexed. Assuming page.page_number is 1-indexed from the frontend
                fitz_page_num = max(0, page.page_number - 1)
                if fitz_page_num >= len(pdf_doc):
                    raise HTTPException(status_code=400, detail="Invalid page number")
                
                pdf_page = pdf_doc[fitz_page_num]
                
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
                        node = annot_service.add_text(
                            page_id=payload.page_id,
                            text=text,
                            x=ocr_data['left'][i],
                            y=ocr_data['top'][i],
                            width=ocr_data['width'][i],
                            height=ocr_data['height'][i]
                        )
                        added_nodes.append(node)

                pdf_doc.close()

                return {
                    "status": "success",
                    "message": f"OCR complete. Added {len(added_nodes)} text nodes.",
                    "nodes": added_nodes
                }

            except Exception as e:
                raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")