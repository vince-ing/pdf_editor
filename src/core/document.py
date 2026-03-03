import fitz
from .page import PDFPage


class PDFDocument:
    """
    Core wrapper for PyMuPDF (fitz) Document.
    Isolates PDF interaction from the rest of the application.
    """

    def __init__(self, path: str = None):
        self.path = path
        if path:
            self._doc = fitz.open(path)
        else:
            self._doc = fitz.open()  # new blank document

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def save(self, output_path: str, incremental: bool = False, deflate: bool = True):
        """Saves the current state of the document to the specified path."""
        if incremental and output_path == self.path:
            self._doc.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        else:
            self._doc.save(output_path, deflate=deflate, garbage=4)

    def close(self):
        """Frees the PDF file from memory."""
        if self._doc and not self._doc.is_closed:
            self._doc.close()

    @property
    def page_count(self) -> int:
        return len(self._doc)

    def get_page(self, index: int) -> PDFPage:
        if index < 0 or index >= self.page_count:
            raise IndexError(f"Page index {index} out of range (0–{self.page_count - 1})")
        return PDFPage(self._doc[index])

    def extract_image_by_xref(self, xref: int) -> dict:
        return self._doc.extract_image(xref)

    def reorder(self, new_order: list):
        self._doc.select(new_order)

    def delete_page(self, page_index: int):
        self._doc.delete_page(page_index)

    def insert_page(self, index: int = -1, width: float = 595, height: float = 842):
        """Inserts a blank A4-sized page at the given index."""
        self._doc.new_page(index, width=width, height=height)

    def get_metadata(self) -> dict:
        return self._doc.metadata

    def get_toc(self) -> list:
        return self._doc.get_toc()