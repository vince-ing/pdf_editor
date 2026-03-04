# src/commands/ocr_page.py
import os
import io
import fitz
import pytesseract
from PIL import Image
from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot

# Dynamically resolve the path to tesseract.exe based on this file's location
# __file__ is src/commands/ocr_page.py
# 2 levels up is the project root (pdf_editor)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
TESSERACT_EXE_PATH = os.path.join(PROJECT_ROOT, "pytesseract", "tesseract.exe")

if os.path.exists(TESSERACT_EXE_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH

class OcrPageCommand(Command):
    """
    Renders an existing PDF page to an image, runs OCR to generate a searchable 
    hidden text layer, and replaces the old page with the new OCR'd page perfectly 
    scaled to the original physical dimensions.
    """

    def __init__(self, document, page_index: int):
        self.document = document
        self.page_index = page_index
        self._snapshot = DocumentSnapshot(document)

    def execute(self):
        doc = self.document._doc
        page = doc[self.page_index]
        
        # 1. Capture the exact physical dimensions of the original page
        original_rect = page.rect
        
        # 2. Render page at 300 DPI for high-accuracy OCR reading
        pix = page.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        
        # 3. Generate new PDF bytes with an invisible text layer over the image
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(img, extension='pdf')
        ocr_pdf = fitz.open("pdf", pdf_bytes)
        
        # 4. Create a new blank page locked to the original physical dimensions
        new_page = doc.new_page(
            self.page_index + 1, 
            width=original_rect.width, 
            height=original_rect.height
        )
        
        # 5. Stamp the Tesseract-generated page onto our correctly sized page
        # This forces the massive 300 DPI output to shrink back down to the 
        # actual document dimensions without losing the high-fidelity text layer.
        new_page.show_pdf_page(new_page.rect, ocr_pdf, 0)
        
        # 6. Delete the old page
        doc.delete_page(self.page_index)
        ocr_pdf.close()

    def undo(self):
        self._snapshot.restore(self.document)

    def cleanup(self):
        self._snapshot.cleanup()