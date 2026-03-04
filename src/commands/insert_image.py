"""
InsertImageCommand — places an image file onto a page region.
Uses DocumentSnapshot for disk-backed undo.
"""

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot


class InsertImageCommand(Command):
    """Inserts an image from disk into a rectangular region on a PDF page."""

    def __init__(
        self,
        image_service,
        document,
        page_index: int,
        rect: tuple,
        image_path: str,
    ):
        self.image_service = image_service
        self.document      = document
        self.page_index    = page_index
        self.rect          = rect          # (x0, y0, x1, y1) PDF points
        self.image_path    = image_path
        self._snapshot     = DocumentSnapshot(document)

    def execute(self):
        self.image_service.insert_image(
            self.document, self.page_index, self.rect, self.image_path,
        )

    def undo(self):
        self._snapshot.restore(self.document)

    def cleanup(self):
        self._snapshot.cleanup()