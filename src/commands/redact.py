"""
RedactCommand — applies a permanent redaction to a single rect on a page.

Because apply_redactions() is irreversible at the PyMuPDF API level,
undo is implemented the same way as all other destructive commands in
this codebase: by restoring a full disk-backed snapshot taken *before*
the redaction was applied.

BulkRedactCommand wraps multiple rects into a single undoable step so
that "Redact All Matches" produces one history entry.
"""

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot


class RedactCommand(Command):
    """
    Permanently redacts a single rectangular region on a page.

    Undo restores the full document from a pre-execute snapshot stored on
    disk (via DocumentSnapshot), keeping RAM usage flat regardless of PDF size.
    """

    def __init__(
        self,
        redaction_service,
        document,
        page_index: int,
        rect: tuple,
        fill_color: tuple = (0.0, 0.0, 0.0),
        replacement_text: str = "",
    ):
        self.redaction_service  = redaction_service
        self.document           = document
        self.page_index         = page_index
        self.rect               = rect
        self.fill_color         = fill_color
        self.replacement_text   = replacement_text
        self._snapshot          = DocumentSnapshot(document)

    def execute(self):
        self.redaction_service.add_redaction(
            self.document,
            self.page_index,
            self.rect,
            fill_color=self.fill_color,
            replacement_text=self.replacement_text,
        )

    def undo(self):
        self._snapshot.restore(self.document)

    def cleanup(self):
        self._snapshot.cleanup()


class BulkRedactCommand(Command):
    """
    Redacts multiple rectangles on a page in a single undoable step.

    All rects must be on the same page — this keeps the snapshot cost to
    one file write regardless of how many matches are redacted at once.
    """

    def __init__(
        self,
        redaction_service,
        document,
        page_index: int,
        rects: list[tuple],
        fill_color: tuple = (0.0, 0.0, 0.0),
        replacement_text: str = "",
    ):
        self.redaction_service  = redaction_service
        self.document           = document
        self.page_index         = page_index
        self.rects              = rects
        self.fill_color         = fill_color
        self.replacement_text   = replacement_text
        self._snapshot          = DocumentSnapshot(document)

    def execute(self):
        for rect in self.rects:
            self.redaction_service.add_redaction(
                self.document,
                self.page_index,
                rect,
                fill_color=self.fill_color,
                replacement_text=self.replacement_text,
            )

    def undo(self):
        self._snapshot.restore(self.document)

    def cleanup(self):
        self._snapshot.cleanup()