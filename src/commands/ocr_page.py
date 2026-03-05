from __future__ import annotations

import io
import os

import fitz
import pytesseract
from PIL import Image

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot
from src.core.document import PDFDocument

# Dynamically resolve the path to tesseract.exe based on this file's location
CURRENT_DIR      = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT     = os.path.dirname(os.path.dirname(CURRENT_DIR))
TESSERACT_EXE_PATH = os.path.join(PROJECT_ROOT, "pytesseract", "tesseract.exe")

if os.path.exists(TESSERACT_EXE_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH


def generate_ocr_pdf_bytes(document: PDFDocument, page_index: int) -> bytes:
    """
    HEAVY WORKER: This function is safe to run in a background thread 
    because it only reads from the document; it does not mutate it.
    """
    doc  = document._doc
    page = doc[page_index]

    # Render page at 300 DPI for high-accuracy OCR reading
    pix = page.get_pixmap(dpi=300)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    # Generate new PDF bytes with an invisible text layer over the image
    return pytesseract.image_to_pdf_or_hocr(img, extension="pdf")


class OcrPageCommand(Command):
    """
    Replaces an existing PDF page with a new OCR'd page using pre-computed PDF bytes.
    This execution is lightning fast and safe for the Tkinter main thread.
    """
    
    label = "OCR Page"

    def __init__(self, document: PDFDocument, page_index: int, ocr_pdf_bytes: bytes) -> None:
        self.document   = document
        self.page_index = page_index
        self.ocr_pdf_bytes = ocr_pdf_bytes
        self._snapshot  = DocumentSnapshot(document)

    def execute(self) -> None:
        doc  = self.document._doc
        page = doc[self.page_index]

        # 1. Capture the exact physical dimensions of the original page
        original_rect = page.rect

        # 2. Open the bytes we generated in the background thread
        ocr_pdf = fitz.open("pdf", self.ocr_pdf_bytes)

        # 3. Create a new blank page locked to the original physical dimensions
        new_page = doc.new_page(
            self.page_index + 1,
            width=original_rect.width,
            height=original_rect.height,
        )

        # 4. Stamp the Tesseract-generated page onto our correctly sized page.
        new_page.show_pdf_page(new_page.rect, ocr_pdf, 0)

        # 5. Delete the old page
        doc.delete_page(self.page_index)
        ocr_pdf.close()

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()