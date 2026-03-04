"""
RedactCommand — applies a permanent redaction to a single rect on a page.

Because apply_redactions() is irreversible at the PyMuPDF API level,
undo is implemented the same way as all other destructive commands in
this codebase: by restoring a full disk-backed snapshot taken *before*
the redaction was applied.

BulkRedactCommand wraps multiple rects into a single undoable step so
that "Redact All Matches" produces one history entry.
"""

from __future__ import annotations

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot
from src.core.document import PDFDocument
from src.services.redaction_service import RedactionService


class RedactCommand(Command):
    """
    Permanently redacts a single rectangular region on a page.

    Undo restores the full document from a pre-execute snapshot stored on
    disk (via DocumentSnapshot), keeping RAM usage flat regardless of PDF size.
    """

    def __init__(
        self,
        redaction_service: RedactionService,
        document: PDFDocument,
        page_index: int,
        rect: tuple[float, float, float, float],
        fill_color: tuple[float, float, float] = (0.0, 0.0, 0.0),
        replacement_text: str = "",
    ) -> None:
        self.redaction_service  = redaction_service
        self.document           = document
        self.page_index         = page_index
        self.rect               = rect
        self.fill_color         = fill_color
        self.replacement_text   = replacement_text
        self._snapshot          = DocumentSnapshot(document)

    def execute(self) -> None:
        self.redaction_service.add_redaction(
            self.document,
            self.page_index,
            self.rect,
            fill_color=self.fill_color,
            replacement_text=self.replacement_text,
        )

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()


class BulkRedactCommand(Command):
    """
    Redacts multiple rectangles on a page in a single undoable step.

    All rects must be on the same page — this keeps the snapshot cost to
    one file write regardless of how many matches are redacted at once.

    Uses ``add_redactions_bulk`` so that all annotations are marked first
    and apply_redactions() is called exactly once. Calling add_redaction()
    in a loop would invoke apply_redactions() once per rect, corrupting
    every match after the first.
    """

    def __init__(
        self,
        redaction_service: RedactionService,
        document: PDFDocument,
        page_index: int,
        rects: list[tuple[float, float, float, float]],
        fill_color: tuple[float, float, float] = (0.0, 0.0, 0.0),
        replacement_text: str = "",
    ) -> None:
        self.redaction_service  = redaction_service
        self.document           = document
        self.page_index         = page_index
        self.rects              = rects
        self.fill_color         = fill_color
        self.replacement_text   = replacement_text
        self._snapshot          = DocumentSnapshot(document)

    def execute(self) -> None:
        self.redaction_service.add_redactions_bulk(
            self.document,
            self.page_index,
            self.rects,
            fill_color=self.fill_color,
            replacement_text=self.replacement_text,
        )

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()