from src.commands.base import Command


class RotatePageCommand(Command):
    """Rotates a page in-place. Undo rotates back — no snapshot needed."""

    def __init__(self, page_service, document, page_index: int, angle: int):
        self.page_service = page_service
        self.document     = document
        self.page_index   = page_index
        self.angle        = angle

    def execute(self):
        self.page_service.rotate_page(self.document, self.page_index, self.angle)

    def undo(self):
        self.page_service.rotate_page(self.document, self.page_index, -self.angle)