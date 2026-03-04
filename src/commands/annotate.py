"""
Annotation commands — highlight and rectangle annotations.
All use DocumentSnapshot for disk-backed undo.
"""

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot


class AddHighlightCommand(Command):
    """Adds a highlight annotation over a rect on a page."""

    def __init__(self, annotation_service, document, page_index: int, rect: tuple):
        self.annotation_service = annotation_service
        self.document   = document
        self.page_index = page_index
        self.rect       = rect
        self._snapshot  = DocumentSnapshot(document)

    def execute(self):
        self.annotation_service.add_highlight(self.document, self.page_index, self.rect)

    def undo(self):
        self._snapshot.restore(self.document)

    def cleanup(self):
        self._snapshot.cleanup()


class AddRectAnnotationCommand(Command):
    """Draws a rectangle annotation on a page."""

    def __init__(
        self,
        annotation_service,
        document,
        page_index: int,
        rect: tuple,
        color: tuple = (1, 0, 0),
        fill: tuple = None,
        width: float = 1.5,
    ):
        self.annotation_service = annotation_service
        self.document   = document
        self.page_index = page_index
        self.rect       = rect
        self.color      = color
        self.fill       = fill
        self.width      = width
        self._snapshot  = DocumentSnapshot(document)

    def execute(self):
        self.annotation_service.add_rect_annotation(
            self.document, self.page_index, self.rect,
            color=self.color, fill=self.fill, width=self.width,
        )

    def undo(self):
        self._snapshot.restore(self.document)

    def cleanup(self):
        self._snapshot.cleanup()