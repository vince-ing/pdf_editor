from src.commands.base import Command


class RotatePageCommand(Command):
    """Command to rotate a specific page in a PDF document."""

    def __init__(self, page_service, document, page_index: int, angle: int):
        self.page_service = page_service
        self.document     = document
        self.page_index   = page_index
        self.angle        = angle

    def execute(self):
        """Applies the rotation."""
        self.page_service.rotate_page(self.document, self.page_index, self.angle)

    def undo(self):
        """Reverses the rotation by rotating in the opposite direction."""
        self.page_service.rotate_page(self.document, self.page_index, -self.angle)