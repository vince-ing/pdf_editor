from engine.src.commands.base import Command
from engine.src.editor.editor_session import EditorSession

class RotatePageCommand(Command):
    """Rotates a page by a specified number of degrees."""
    def __init__(self, page_id: str, degrees: int = 90):
        self.page_id = page_id
        self.degrees = degrees

    def execute(self, session: EditorSession) -> None:
        page = session.document.get_child(self.page_id)
        if not page or page.node_type != "page":
            raise ValueError(f"Page with ID {self.page_id} not found.")
        
        # Keep rotation within 0-359 degrees
        page.rotation = (page.rotation + self.degrees) % 360

    def undo(self, session: EditorSession) -> None:
        page = session.document.get_child(self.page_id)
        if page:
            page.rotation = (page.rotation - self.degrees) % 360