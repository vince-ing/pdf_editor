import fitz
from .page import PDFPage

class PDFDocument:
    """
    Core wrapper for PyMuPDF (fitz) Document.
    Isolates PDF interaction from the rest of the application.
    """
    def __init__(self, path: str):
        self.path = path
        self._doc = fitz.open(path)

    def __enter__(self):
        """Enable context manager support (with PDFDocument(...) as doc:)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure the document is safely closed when exiting the context."""
        self.close()

    def save(self, output_path: str):
        """Saves the current state of the document to the specified path."""
        self._doc.save(output_path)

    def close(self):
        """Frees the PDF file from memory."""
        if not self._doc.is_closed:
            self._doc.close()

    @property
    def page_count(self) -> int:
        """Returns the total number of pages."""
        return len(self._doc)

    def get_page(self, index: int) -> PDFPage:
        """Retrieves a specific page wrapped in our PDFPage class."""
        return PDFPage(self._doc[index])

    def extract_image_by_xref(self, xref: int) -> dict:
        """
        Extracts raw image data and metadata using its cross-reference number.
        Returns a dict containing 'ext' (extension) and 'image' (bytes).
        """
        return self._doc.extract_image(xref)

    def reorder(self, new_order: list[int]):
        """
        Reorders, duplicates, or deletes pages in place.
        :param new_order: A list of 0-based page indices (e.g., [2, 0, 1]).
        """
        # PyMuPDF's select() is highly optimized for this exact operation
        self._doc.select(new_order)