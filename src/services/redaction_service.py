"""
RedactionService — applies permanent content redaction to PDF pages.

Redaction is a two-step process in PyMuPDF:
  1. Mark rectangles as redaction annotations.
  2. Call page.apply_redactions() to permanently burn them in —
     removing underlying text, images, and vector graphics.

This is fundamentally different from drawing a black rectangle on top:
the underlying content is *destroyed*, so it cannot be copy-pasted,
searched, or extracted by any downstream tool.

Compatibility note
------------------
PyMuPDF named the redaction integer constants (PDF_REDACT_IMAGE_PIXELS,
PDF_REDACT_LINE_ART_IF_COVERED, etc.) only in newer releases. Older builds
expose the same integers but not as module-level attributes. We therefore
define the values ourselves so the code runs on any PyMuPDF version that
supports apply_redactions() at all (≥ 1.18).

Integer reference (from PyMuPDF source, stable across versions):
  images  arg:  0 = none, 1 = blank, 2 = pixels (blank image data)
  graphics arg: 0 = none, 1 = if_covered, 2 = all
"""

import fitz

from src.core.document import PDFDocument

# ── version-safe redaction constants ─────────────────────────────────────────
# Use named attribute when available; fall back to the raw integer so we work
# on every PyMuPDF release that has apply_redactions().
_REDACT_IMAGE_PIXELS        = getattr(fitz, "PDF_REDACT_IMAGE_PIXELS",        2)
_REDACT_LINE_ART_IF_COVERED = getattr(fitz, "PDF_REDACT_LINE_ART_IF_COVERED", 1)


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
        page      = document._doc[page_index]
        fitz_rect = fitz.Rect(*rect)

        page.add_redact_annot(
            quad=fitz_rect,
            fill=list(fill_color),
            text=replacement_text if replacement_text else None,
            fontsize=10 if replacement_text else 0,
        )

        # This is the step that makes redaction permanent and irreversible.
        # The kwargs were added in PyMuPDF 1.21; on older builds we call with
        # no arguments (text is still removed unconditionally).
        try:
            page.apply_redactions(
                images=_REDACT_IMAGE_PIXELS,
                graphics=_REDACT_LINE_ART_IF_COVERED,
            )
        except TypeError:
            # PyMuPDF < 1.21 — apply_redactions() takes no keyword arguments
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
        page  = document._doc[page_index]
        flags = 0 if case_sensitive else getattr(fitz, "TEXT_DEHYPHENATE", 0)
        quads = page.search_for(
            query,
            quads=True,
            flags=flags,
        )
        # Convert each Quad to a Rect tuple
        return [tuple(q.rect) for q in quads]