"""
AnnotationService — business logic for highlight and rectangle annotations.
Coordinates between the GUI/commands and the core PDFPage wrapper.
"""

from src.core.document import PDFDocument


class AnnotationService:
    """Handles adding and removing annotations on PDF pages."""

    def add_highlight(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
    ):
        """
        Adds a yellow highlight annotation over the given rect.
        rect: (x0, y0, x1, y1) in PDF user-space points.
        """
        import fitz
        page = document.get_page(page_index)
        quad = fitz.Rect(*rect).quad
        page.add_highlight(quad)

    def add_rect_annotation(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
        color: tuple = (1, 0, 0),
        fill: tuple = None,
        width: float = 1.5,
    ):
        """
        Draws a rectangle annotation on the page.
        color / fill: RGB tuples with values 0.0–1.0.
        """
        page = document.get_page(page_index)
        page.add_rect_annotation(rect, color=color, fill=fill, width=width)