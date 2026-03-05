"""
TocService — business logic for reading and writing a PDF's table of contents.

PyMuPDF represents a TOC as a list of [level, title, page_number] entries
where level is 1-based (1 = top-level chapter) and page_number is 1-based.

All validation and normalisation lives here so no other layer needs to import
fitz or reason about the TOC list format.
"""

from __future__ import annotations

from src.core.document import PDFDocument


class TocService:
    """Fetch and persist the table of contents for a PDF document."""

    # ── read ──────────────────────────────────────────────────────────────────

    def get_toc(self, document: PDFDocument) -> list[list]:
        """
        Return the document outline as ``[[level, title, page], …]``.

        *level* starts at 1 (top-level entry). *page* is 1-based.
        Returns an empty list when the document has no outline.
        """
        return document.get_toc()

    # ── write ─────────────────────────────────────────────────────────────────

    def set_toc(self, document: PDFDocument, toc: list[list]) -> None:
        """
        Replace the document's outline with *toc*.

        Validates that every entry is well-formed and that page numbers are
        within the document's range before writing; raises ``ValueError`` with
        a descriptive message on the first bad entry.

        Parameters
        ----------
        toc : list of [level, title, page]
            Pass an empty list to clear the outline entirely.
        """
        self._validate(document, toc)
        document.set_toc(toc)

    # ── validation ────────────────────────────────────────────────────────────

    def _validate(self, document: PDFDocument, toc: list[list]) -> None:
        page_count = document.page_count

        for i, entry in enumerate(toc):
            if not isinstance(entry, (list, tuple)) or len(entry) < 3:
                raise ValueError(
                    f"TOC entry {i} must be [level, title, page]; got {entry!r}"
                )
            level, title, page = entry[0], entry[1], entry[2]

            if not isinstance(level, int) or level < 1:
                raise ValueError(
                    f"TOC entry {i}: level must be a positive integer, got {level!r}"
                )
            if not isinstance(title, str):
                raise ValueError(
                    f"TOC entry {i}: title must be a string, got {title!r}"
                )
            if not isinstance(page, int) or page < 1:
                raise ValueError(
                    f"TOC entry {i}: page must be a positive integer, got {page!r}"
                )
            if page > page_count:
                raise ValueError(
                    f"TOC entry {i} ({title!r}): page {page} exceeds "
                    f"document page count ({page_count})"
                )

    # ── convenience helpers ───────────────────────────────────────────────────

    @staticmethod
    def normalize_levels(toc: list[list]) -> list[list]:
        """
        Ensure that no entry's level jumps by more than 1 relative to its
        predecessor.  Clamps level to the valid range ``[1, prev_level + 1]``.
        Returns a new list; the input is not mutated.
        """
        result: list[list] = []
        prev_level = 0
        for entry in toc:
            level = max(1, min(entry[0], prev_level + 1))
            result.append([level, entry[1], entry[2]])
            prev_level = level
        return result