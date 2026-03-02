from src.core.document import PDFDocument

class TextService:
    """
    Handles business logic for inserting and manipulating text in PDFs.
    """
    def insert_text(
        self,
        document: PDFDocument,
        page_index: int,
        text: str,
        position: tuple[float, float],
        fontsize: int = 12,
    ):
        """
        Inserts a string of text onto a specific page.
        position: (x, y) coordinates starting from the top-left of the page.
        """
        page = document.get_page(page_index)
        page.insert_text(position, text, fontsize=fontsize)