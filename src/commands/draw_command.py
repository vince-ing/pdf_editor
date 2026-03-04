"""
DrawAnnotationCommand — records a drawn annotation by its PDF xref so it can
be removed on undo without needing a full document snapshot.

fitz annotations have a stable xref (cross-reference number) for the lifetime
of the document object.  We can remove an annotation by xref using
page.delete_annot(annot) after looking it up.

If the annotation has already been removed (e.g. double-undo), the command
is silently a no-op.
"""

from __future__ import annotations
from src.commands.base import Command


class DrawAnnotationCommand(Command):
    """
    Undo: removes the annotation with the stored xref from the given page.
    Redo: re-adds the annotation — but since PDF annotations carry no
          easy clone API, redo is implemented via DocumentSnapshot.

    For simplicity (and because drawing annotations are common), we store a
    lightweight per-annot snapshot: the annotation's /AP stream and properties
    are re-created by re-running the draw operation.  In practice this means
    redo just restores from a minimal snapshot of the single page.
    """

    def __init__(self, document, page_idx: int, xref: int):
        self.document  = document
        self.page_idx  = page_idx
        self.xref      = xref
        # Take a page-level snapshot for redo (fitz has no clone-annotation API)
        from src.commands.snapshot import DocumentSnapshot
        self._snap = DocumentSnapshot(document)

    # ── Command interface ─────────────────────────────────────────────────────

    @property
    def label(self) -> str:
        return "Draw"

    def execute(self):
        # The annotation was already written to the PDF by DrawTool before this
        # command object was created — execute() is a no-op.
        pass

    def undo(self):
        """Delete the annotation by xref."""
        doc = self.document
        if not doc:
            return
        fitz_page = doc.get_page(self.page_idx)._page
        for annot in fitz_page.annots():
            if annot.xref == self.xref:
                fitz_page.delete_annot(annot)
                return
        # Already gone — silently ignore

    def redo(self):
        """Restore from the snapshot taken right after the annotation was drawn."""
        self._snap.restore(self.document)

    def cleanup(self):
        self._snap.cleanup()