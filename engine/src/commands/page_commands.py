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

class DeletePageCommand(Command):
    """Deletes a page from the document."""
    def __init__(self, page_id: str):
        self.page_id = page_id
        self.deleted_page = None
        self.original_index = -1

    def execute(self, session: EditorSession) -> None:
        page = session.document.get_child(self.page_id)
        if not page or page.node_type != "page":
            raise ValueError(f"Page with ID {self.page_id} not found.")
        
        self.deleted_page = page
        self.original_index = session.document.children.index(page)
        session.document.children.remove(page)

    def undo(self, session: EditorSession) -> None:
        if self.deleted_page and self.original_index != -1:
            session.document.children.insert(self.original_index, self.deleted_page)


class MovePageCommand(Command):
    """Moves a page to a new index in the document."""
    def __init__(self, page_id: str, new_index: int):
        self.page_id = page_id
        self.new_index = new_index
        self.old_index = -1

    def execute(self, session: EditorSession) -> None:
        page = session.document.get_child(self.page_id)
        if not page or page.node_type != "page":
            raise ValueError(f"Page with ID {self.page_id} not found.")
        
        self.old_index = session.document.children.index(page)
        session.document.children.remove(page)
        
        # Ensure new_index is within bounds
        target_index = max(0, min(self.new_index, len(session.document.children)))
        session.document.children.insert(target_index, page)

    def undo(self, session: EditorSession) -> None:
        if self.old_index != -1:
            page = session.document.get_child(self.page_id)
            if page:
                session.document.children.remove(page)
                session.document.children.insert(self.old_index, page)