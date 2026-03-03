from src.core.document import PDFDocument


class PageService:
    """
    Handles business logic for page-level PDF operations.
    """

    def rotate_page(self, document: PDFDocument, page_index: int, angle: int):
        """Rotates a specific page in the document."""
        page = document.get_page(page_index)
        page.rotate(angle)

    def reorder_pages(self, document: PDFDocument, new_order: list):
        """
        Reorders, duplicates, or deletes pages in the document.
        new_order: List of 0-based page indices.
        """
        document.reorder(new_order)

    def delete_page(self, document: PDFDocument, page_index: int):
        """Deletes a specific page from the document."""
        document.delete_page(page_index)

    def insert_blank_page(
        self,
        document: PDFDocument,
        index: int = -1,
        width: float = 595,
        height: float = 842,
    ):
        """Inserts a blank page at the given index."""
        document.insert_page(index, width=width, height=height)