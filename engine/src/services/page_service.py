from typing import Optional
from engine.src.editor.editor_session import EditorSession
from engine.src.core.page_node import PageNode
from engine.src.commands.node_commands import AddNodeCommand
from engine.src.commands.page_commands import RotatePageCommand, DeletePageCommand, MovePageCommand

class PageService:
    """
    Coordinates page-level operations for the API.
    All mutations go through self.session.execute() so the undo stack is maintained.
    """
    def __init__(self, session: EditorSession):
        self.session = session

    def add_page(self, page_number: int, source_ref: Optional[str] = None) -> PageNode:
        """Creates a new page node and appends it to the document root."""
        page = PageNode(page_number=page_number, source_reference=source_ref)
        command = AddNodeCommand(parent_id=self.session.document.id, new_node=page)
        self.session.execute(command)
        return page

    def rotate_page(self, page_id: str, degrees: int = 90) -> PageNode:
        """Executes a rotation command and returns the updated page."""
        command = RotatePageCommand(page_id=page_id, degrees=degrees)
        self.session.execute(command)
        return self.session.document.get_child(page_id)

    def delete_page(self, page_id: str) -> bool:
        """Deletes a page via the session so it lands on the undo stack."""
        command = DeletePageCommand(page_id)
        self.session.execute(command)
        return True

    def move_page(self, page_id: str, new_index: int) -> bool:
        """Moves a page to new_index via the session so it lands on the undo stack."""
        command = MovePageCommand(page_id, new_index)
        self.session.execute(command)
        return True