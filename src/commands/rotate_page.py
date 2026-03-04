from __future__ import annotations

from src.commands.base import Command
from src.core.document import PDFDocument
from src.services.page_service import PageService


class RotatePageCommand(Command):
    """Rotates a page in-place. Undo rotates back — no snapshot needed."""

    def __init__(
        self,
        page_service: PageService,
        document: PDFDocument,
        page_index: int,
        angle: int,
    ) -> None:
        self.page_service = page_service
        self.document     = document
        self.page_index   = page_index
        self.angle        = angle

    def execute(self) -> None:
        self.page_service.rotate_page(self.document, self.page_index, self.angle)

    def undo(self) -> None:
        self.page_service.rotate_page(self.document, self.page_index, -self.angle)

    def cleanup(self) -> None:
        pass  # no resources to free