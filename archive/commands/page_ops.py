"""
Page operation commands — reorder and duplicate.

ReorderPagesCommand  — no snapshot needed; undo is the inverse permutation.
DuplicatePageCommand — uses insert_pdf() via a temp document (safe fitz API),
                       with DocumentSnapshot for undo.
"""

from __future__ import annotations

import fitz

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot
from src.core.document import PDFDocument


class ReorderPagesCommand(Command):
    """
    Reorders document pages according to new_order.

    new_order is a list of original 0-based page indices in their desired
    positions, e.g. [2, 0, 1] puts the old page 2 first.

    Undo is the inverse permutation — no snapshot file needed.
    All indices in new_order must be unique (no duplication).
    """

    def __init__(self, document: PDFDocument, new_order: list[int]) -> None:
        self.document  = document
        self.new_order = list(new_order)
        n = len(new_order)
        # Build inverse permutation for undo
        self._inv_order: list[int] = [0] * n
        for dest, src in enumerate(new_order):
            self._inv_order[src] = dest

    def execute(self) -> None:
        self.document.reorder(self.new_order)

    def undo(self) -> None:
        self.document.reorder(self._inv_order)

    def cleanup(self) -> None:
        pass  # no resources to free


class DuplicatePageCommand(Command):
    """
    Inserts a copy of page *src_index* immediately after itself.

    Uses insert_pdf() via a temporary in-memory document rather than
    select() with a repeated index.  Inserting a fitz document into itself
    is explicitly unsafe; copying through a temp doc is the correct approach.

    Undo restores the full document from a pre-execute snapshot.
    """

    def __init__(self, document: PDFDocument, src_index: int) -> None:
        self.document   = document
        self.src_index  = src_index
        # Snapshot taken before execute so undo can restore exactly
        self._snapshot  = DocumentSnapshot(document)

    def execute(self) -> None:
        """
        Copy src_index to a temporary fitz document, then insert that
        single-page doc back into the source document right after src_index.
        """
        src = self.src_index
        doc = self.document._doc

        # Step 1: copy the page into a fresh in-memory document
        tmp = fitz.open()
        try:
            tmp.insert_pdf(doc, from_page=src, to_page=src)
            # Step 2: insert that copy back right after the original
            doc.insert_pdf(tmp, from_page=0, to_page=0, start_at=src + 1)
        finally:
            tmp.close()

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()