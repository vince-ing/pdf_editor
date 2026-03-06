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
CURRENT_DIR        = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT       = os.path.dirname(os.path.dirname(CURRENT_DIR))
TESSERACT_EXE_PATH = os.path.join(PROJECT_ROOT, "pytesseract", "tesseract.exe")

if os.path.exists(TESSERACT_EXE_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH

# Minimum Tesseract word confidence to accept (0-100)
_MIN_CONFIDENCE = 30

# DPI to render regions for Tesseract
_OCR_DPI = 300

# Gaps between text blocks larger than this are treated as figure regions
_MIN_FIGURE_GAP_PT = 60.0


def _find_figure_regions(page: fitz.Page) -> list[fitz.Rect]:
    """
    Find regions of the page that contain images.
    
    Uses PyMuPDF's get_image_info() to locate the bounding boxes 
    of all images displayed on the page.
    """
    figure_rects: list[fitz.Rect] = []
    
    # get_image_info() returns a list of dictionaries. Each dictionary 
    # contains a 'bbox' key with a tuple of coordinates: (x0, y0, x1, y1)
    for img_info in page.get_image_info():
        bbox = img_info.get("bbox")
        if bbox:
            figure_rects.append(fitz.Rect(bbox))
            
    return figure_rects


def _ocr_region(page: fitz.Page, clip: fitz.Rect) -> list[dict]:
    """
    Render one region of the page at 300 DPI, run Tesseract, group words by line,
    and return text dicts with PDF-space coordinates.
    """
    mat   = fitz.Matrix(_OCR_DPI / 72, _OCR_DPI / 72)
    pix   = page.get_pixmap(matrix=mat, clip=clip)
    img   = Image.open(io.BytesIO(pix.tobytes("png")))
    scale = _OCR_DPI / 72.0

    data = pytesseract.image_to_data(
        img,
        output_type=pytesseract.Output.DICT,
        config="--psm 3",
    )

    lines = {}
    
    for i in range(len(data["text"])):
        word = data["text"][i].strip()
        if not word:
            continue
            
        try:
            conf = int(data["conf"][i])
        except (ValueError, TypeError):
            conf = 0
            
        if conf < _MIN_CONFIDENCE:
            continue

        # Create a unique identifier for this specific line of text
        block_num = data["block_num"][i]
        par_num   = data["par_num"][i]
        line_num  = data["line_num"][i]
        line_id   = (block_num, par_num, line_num)

        px_h     = data["height"][i]
        pdf_x    = clip.x0 + data["left"][i] / scale
        pdf_y    = clip.y0 + (data["top"][i] + px_h * 0.85) / scale
        fontsize = max(4.0, px_h / scale * 0.85)

        if line_id not in lines:
            # First word in this line, establish the starting coordinates
            lines[line_id] = {
                "text": word,
                "x": pdf_x,
                "y": pdf_y,
                "fontsize": fontsize
            }
        else:
            # Append subsequent words with a space
            lines[line_id]["text"] += " " + word
            # Use the largest font size found on this line to ensure the bounding box fits
            if fontsize > lines[line_id]["fontsize"]:
                lines[line_id]["fontsize"] = fontsize

    # Flatten the grouped lines back into a list of dictionaries
    return list(lines.values())


def generate_ocr_data(document: PDFDocument, page_index: int) -> list[dict] | None:
    """
    HEAVY WORKER — safe to run in a background thread (read-only).

    Detects figure regions on the page (large vertical gaps between text blocks),
    runs Tesseract on each one, and returns word dicts with PDF-space coordinates.

    Returns None if no figure regions are found (text-only page).
    """
    doc  = document._doc
    page = doc[page_index]

    figure_rects = _find_figure_regions(page)
    print(f"[OCR DEBUG] page {page_index}: {len(figure_rects)} figure region(s)")
    for r in figure_rects:
        print(f"  region: {[round(x,1) for x in [r.x0,r.y0,r.x1,r.y1]]} ({r.width:.0f}x{r.height:.0f}pt)")
    if not figure_rects:
        print(f"  -> no figure regions found, skipping")
        return None

    all_words: list[dict] = []
    for rect in figure_rects:
        words = _ocr_region(page, rect)
        print(f"  region {[round(x,1) for x in [rect.x0,rect.y0,rect.x1,rect.y1]]}: {len(words)} words found")
        if words:
            print(f"    first 3: {[w['text'] for w in words[:3]]}")
        all_words.extend(words)

    print(f"  -> total {len(all_words)} words to insert")
    return all_words if all_words else None


class OcrPageCommand(Command):
    """
    Adds an invisible OCR text layer over figure regions of a page.

    Never replaces or modifies any existing page content — only inserts
    invisible text spans (render_mode=3) over the detected figure areas,
    leaving all existing text, images, and layout completely untouched.

    If ocr_words is None execute() is a no-op.
    """

    label = "OCR Page"

    def __init__(
        self,
        document: PDFDocument,
        page_index: int,
        ocr_words: list[dict] | None,
    ) -> None:
        self.document   = document
        self.page_index = page_index
        self.ocr_words  = ocr_words
        self._snapshot  = DocumentSnapshot(document)

    def execute(self) -> None:
        if not self.ocr_words:
            return

        page = self.document.get_page(self.page_index)
        for word in self.ocr_words:
            try:
                page.insert_text(
                    (word["x"], word["y"]),
                    word["text"],
                    fontsize=word["fontsize"],
                    fontname="helv",
                    color=(0, 0, 0),
                    render_mode=3,  # invisible — text layer only, no visible ink
                )
            except Exception:
                pass

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()