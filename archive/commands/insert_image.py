"""
InsertImageCommand — places an image file onto a page region.
Uses DocumentSnapshot for disk-backed undo.
"""

from __future__ import annotations

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot
from src.core.document import PDFDocument
from src.services.image_service import ImageService


class InsertImageCommand(Command):
    """Inserts an image from disk into a rectangular region on a PDF page."""

    def __init__(
        self,
        image_service: ImageService,
        document: PDFDocument,
        page_index: int,
        rect: tuple[float, float, float, float],
        image_path: str,
    ) -> None:
        self.image_service = image_service
        self.document      = document
        self.page_index    = page_index
        self.rect          = rect          # (x0, y0, x1, y1) PDF points
        self.image_path    = image_path
        self._snapshot     = DocumentSnapshot(document)

    def execute(self) -> None:
        self.image_service.insert_image(
            self.document, self.page_index, self.rect, self.image_path,
        )

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()