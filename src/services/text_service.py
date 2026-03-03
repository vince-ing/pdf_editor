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
        position: tuple,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple = (0, 0, 0),
    ):
        """
        Inserts a string of text onto a specific page at (x, y) from top-left.
        color: RGB tuple with values in range 0.0–1.0.
        """
        page = document.get_page(page_index)
        page.insert_text(position, text, fontsize=fontsize, fontname=fontname, color=color)

    def insert_textbox(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple = (0, 0, 0),
        align: int = 0,
    ) -> float:
        """
        Inserts text into a bounded rectangle.
        Returns the unused space (negative = overflow).
        """
        page = document.get_page(page_index)
        return page.insert_textbox(rect, text, fontsize=fontsize, fontname=fontname,
                                   color=color, align=align)