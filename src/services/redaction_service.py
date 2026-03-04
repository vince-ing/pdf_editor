"""
RedactionService — applies permanent content redaction to PDF pages.

Redaction is a two-step process in PyMuPDF:
  1. Mark rectangles as redaction annotations.
  2. Call page.apply_redactions() to permanently burn them in —
     removing underlying text, images, and vector graphics.

This is fundamentally different from drawing a black rectangle on top:
the underlying content is *destroyed*, so it cannot be copy-pasted,
searched, or extracted by any downstream tool.

All fitz-level operations are delegated to PDFPage methods so this
service never touches document._doc directly.
"""

from src.core.document import PDFDocument


class RedactionService:
    """Applies permanent content redactions to a PDF page."""

    DEFAULT_FILL = (0.0, 0.0, 0.0)   # black

    def add_redaction(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
        fill_color: tuple = DEFAULT_FILL,
        replacement_text: str = "",
    ) -> None:
        """
        Mark *rect* as a redaction annotation and immediately apply it so the
        underlying content is permanently destroyed.

        For redacting a single rect. Use ``add_redactions_bulk`` when you need
        to redact multiple rects in one pass — calling this method in a loop
        would call apply_redactions() once per rect, which corrupts the page.

        Parameters
        ----------
        document : PDFDocument
        page_index : int
            0-based page index.
        rect : tuple
            (x0, y0, x1, y1) in PDF user-space points.
        fill_color : tuple
            RGB 0.0–1.0 fill for the burnt-in box. Defaults to black.
        replacement_text : str
            Optional label drawn on the redaction box (e.g. "[REDACTED]").
            Empty string means no label.
        """
        page = document.get_page(page_index)
        page.add_redact_annot(rect, fill_color=fill_color, replacement_text=replacement_text)
        page.apply_redactions()

    def add_redactions_bulk(
        self,
        document: PDFDocument,
        page_index: int,
        rects: list[tuple],
        fill_color: tuple = DEFAULT_FILL,
        replacement_text: str = "",
    ) -> None:
        """
        Mark all *rects* as redaction annotations, then apply them all in a
        single pass so every match is burnt in correctly.

        Calling ``add_redaction`` in a loop is incorrect: each call would
        invoke apply_redactions() immediately, leaving subsequent annots in an
        undefined state. This method marks every rect first, then applies once.

        Parameters
        ----------
        document : PDFDocument
        page_index : int
            0-based page index.
        rects : list of (x0, y0, x1, y1) tuples in PDF user-space points.
        fill_color : tuple
            RGB 0.0–1.0 fill for all boxes. Defaults to black.
        replacement_text : str
            Optional label drawn on every box. Empty string means no label.
        """
        page = document.get_page(page_index)
        for rect in rects:
            page.add_redact_annot(rect, fill_color=fill_color, replacement_text=replacement_text)
        page.apply_redactions()

    def find_text(
        self,
        document: PDFDocument,
        page_index: int,
        query: str,
        case_sensitive: bool = False,
    ) -> list[tuple]:
        """
        Search for *query* on a page and return bounding rects for every hit.

        Returns
        -------
        list of (x0, y0, x1, y1) tuples in PDF user-space points.
        """
        page = document.get_page(page_index)
        return page.search_text_quads(query, case_sensitive=case_sensitive)