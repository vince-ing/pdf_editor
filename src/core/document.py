from __future__ import annotations

import fitz
from .page import PDFPage


class PDFDocument:
    """
    Core wrapper for PyMuPDF (fitz) Document.
    Isolates PDF interaction from the rest of the application.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path: str | None = path
        self._doc: fitz.Document
        if path:
            self._doc = fitz.open(path)
        else:
            self._doc = fitz.open()  # new blank document

    def __enter__(self) -> PDFDocument:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def can_save_incrementally(self) -> bool:
        """
        Return True only when an incremental save is safe to attempt.

        PyMuPDF refuses incremental saves — and may corrupt the file — when:
          • The document was never opened from disk (no path).
          • The document has been restructured (pages deleted, reordered,
            or inserted), which fitz tracks internally.
          • The document was decrypted (encryption state would be inconsistent).
          • The document is not a PDF (e.g. XPS opened via fitz).

        Calling fitz's own can_save_incrementally() is the authoritative check;
        we guard with a hasattr so the code degrades gracefully on very old
        PyMuPDF builds that predate the method.
        """
        if not self.path:
            return False
        if hasattr(self._doc, "can_save_incrementally"):
            return self._doc.can_save_incrementally()
        return True

    def save(
        self,
        output_path: str,
        incremental: bool = False,
        deflate: bool = True,
    ) -> None:
        """
        Save the document to *output_path*.

        When *incremental* is True the caller is requesting an in-place update,
        but we honour that only when ``can_save_incrementally()`` agrees it is
        safe.
        """
        if incremental and output_path == self.path and self.can_save_incrementally():
            self._doc.save(output_path, incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        else:
            self._doc.save(output_path, deflate=deflate, garbage=4)

    def close(self) -> None:
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

    def reorder(self, new_order: list[int]) -> None:
        self._doc.select(new_order)

    def delete_page(self, page_index: int) -> None:
        self._doc.delete_page(page_index)

    def insert_page(
        self,
        index: int = -1,
        width: float = 595,
        height: float = 842,
    ) -> None:
        """Inserts a blank A4-sized page at the given index."""
        self._doc.new_page(index, width=width, height=height)

    def get_metadata(self) -> dict[str, str]:
        return self._doc.metadata

    def get_toc(self) -> list[list]:
        """
        Return the document's table of contents as a list of
        [level, title, page_number] entries (1-based page numbers).

        Returns an empty list if the document has no outline.
        """
        return self._doc.get_toc()

    def set_toc(self, toc: list[list]) -> None:
        """
        Replace the document's table of contents.

        Parameters
        ----------
        toc : list of [level, title, page_number]
            PyMuPDF-compatible TOC list.  Level is 1-based (1 = top level).
            Page numbers are 1-based.  Pass an empty list to clear the TOC.
        """
        self._doc.set_toc(toc)