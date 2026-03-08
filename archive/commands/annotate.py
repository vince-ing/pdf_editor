"""
Annotation commands — highlight and rectangle annotations.
All use DocumentSnapshot for disk-backed undo.
"""

from __future__ import annotations

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot
from src.core.document import PDFDocument
from src.services.annotation_service import AnnotationService


class AddHighlightCommand(Command):
    """Adds a highlight annotation over a rect on a page."""

    def __init__(
        self,
        annotation_service: AnnotationService,
        document: PDFDocument,
        page_index: int,
        rect: tuple[float, float, float, float],
    ) -> None:
        self.annotation_service = annotation_service
        self.document   = document
        self.page_index = page_index
        self.rect       = rect
        self._snapshot  = DocumentSnapshot(document)

    def execute(self) -> None:
        self.annotation_service.add_highlight(self.document, self.page_index, self.rect)

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()


class AddRectAnnotationCommand(Command):
    """Draws a rectangle annotation on a page."""

    def __init__(
        self,
        annotation_service: AnnotationService,
        document: PDFDocument,
        page_index: int,
        rect: tuple[float, float, float, float],
        color: tuple[float, float, float] = (1, 0, 0),
        fill: tuple[float, float, float] | None = None,
        width: float = 1.5,
    ) -> None:
        self.annotation_service = annotation_service
        self.document   = document
        self.page_index = page_index
        self.rect       = rect
        self.color      = color
        self.fill       = fill
        self.width      = width
        self._snapshot  = DocumentSnapshot(document)

    def execute(self) -> None:
        self.annotation_service.add_rect_annotation(
            self.document, self.page_index, self.rect,
            color=self.color, fill=self.fill, width=self.width,
        )

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()