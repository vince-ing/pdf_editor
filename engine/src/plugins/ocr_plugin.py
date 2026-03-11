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
            Executes high-resolution OCR on a specific page and adds the detected text 
            to the Scene Graph as invisible, selectable TextNodes using pytesseract.
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
                
                # 1. Render at 300 DPI for high accuracy
                zoom_factor = 300.0 / 72.0
                pix = pdf_page.get_pixmap(matrix=fitz.Matrix(zoom_factor, zoom_factor))
                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                # 2. Execute OCR with --psm 3 and extract word-level data
                ocr_data = pytesseract.image_to_data(
                    img, 
                    lang=payload.language, 
                    output_type=pytesseract.Output.DICT,
                    config="--psm 3"
                )

                annot_service = AnnotationService(session)
                added_nodes = []
                n_boxes = len(ocr_data['text'])

                # 3. Add individual words to prevent coordinate drift and misses
                for i in range(n_boxes):
                    word = ocr_data['text'][i].strip()
                    if not word:
                        continue
                    
                    try:
                        conf = int(ocr_data['conf'][i])
                    except (ValueError, TypeError):
                        conf = 0
                    
                    # Filter out low confidence hits
                    if conf < 30:
                        continue

                    # 4. Scale coordinates back down to the original PDF space
                    px_h = ocr_data['height'][i]
                    x = ocr_data['left'][i] / zoom_factor
                    y = ocr_data['top'][i] / zoom_factor
                    width = ocr_data['width'][i] / zoom_factor
                    height = px_h / zoom_factor
                    
                    # Calculate font size to match the word height in PDF space
                    fontsize = max(4.0, height * 0.85)

                    node = annot_service.add_text(
                        page_id=payload.page_id,
                        text=word,
                        x=x,
                        y=y,
                        width=width,
                        height=height,
                        font_size=fontsize,
                        # 5. Use transparent color to make text selectable but invisible
                        color="transparent" 
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