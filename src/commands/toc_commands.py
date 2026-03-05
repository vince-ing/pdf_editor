"""
toc_commands.py — Undo/redo-capable command for modifying a PDF's table of
contents.

Follows the same Command protocol used by the rest of the application:
  • execute()  — apply the change and snapshot the previous state for undo
  • undo()     — restore the old TOC
  • redo()     — re-apply the new TOC
  • cleanup()  — no-op (nothing to clean up for a TOC edit)
"""

from __future__ import annotations

from src.core.document import PDFDocument
from src.services.toc_service import TocService


class ModifyTocCommand:
    """
    Command that replaces a document's table of contents.

    Parameters
    ----------
    document : PDFDocument
        The open document to modify.
    toc_service : TocService
        Service used to read / write the outline.
    new_toc : list of [level, title, page]
        The desired TOC state.  Pass an empty list to clear the outline.
    """

    label = "Edit Table of Contents"

    def __init__(
        self,
        document: PDFDocument,
        toc_service: TocService,
        new_toc: list[list],
    ) -> None:
        self._document    = document
        self._toc_service = toc_service
        self._new_toc     = new_toc
        self._old_toc: list[list] = []

    # ── Command protocol ──────────────────────────────────────────────────────

    def execute(self) -> None:
        """Snapshot the current TOC then apply the new one."""
        self._old_toc = self._toc_service.get_toc(self._document)
        self._toc_service.set_toc(self._document, self._new_toc)

    def undo(self) -> str:
        """Restore the TOC that existed before execute() was called."""
        self._toc_service.set_toc(self._document, self._old_toc)
        return self.label

    def redo(self) -> str:
        """Re-apply the new TOC."""
        self._toc_service.set_toc(self._document, self._new_toc)
        return self.label

    def cleanup(self) -> None:
        """No temporary resources to release."""