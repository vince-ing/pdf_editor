from src.core.document import PDFDocument

class PageService:
    """
    Handles business logic for page-level PDF operations.
    """
    def rotate_page(self, document: PDFDocument, page_index: int, angle: int):
        """Rotates a specific page in the document."""
        page = document.get_page(page_index)
        page.rotate(angle)

    def reorder_pages(self, document: PDFDocument, new_order: list[int]):
        """
        Reorders, duplicates, or deletes pages in the document.
        new_order: List of 0-based page indices.
        """
        # Relies on our highly optimized PyMuPDF core select() wrapper
        document.reorder(new_order)