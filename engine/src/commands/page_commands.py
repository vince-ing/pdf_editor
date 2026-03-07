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
        page.rotation = (page.rotation + self.degrees) % 360

    def undo(self, session: EditorSession) -> None:
        page = session.document.get_child(self.page_id)
        if page:
            page.rotation = (page.rotation - self.degrees) % 360


class DeletePageCommand(Command):
    """Deletes a page from the document by ID (not object identity)."""
    def __init__(self, page_id: str):
        self.page_id = page_id
        self.deleted_page = None
        self.original_index = -1

    def execute(self, session: EditorSession) -> None:
        # Find index by ID — never use list.index(obj) with Pydantic models
        # because Pydantic v2 may return different instances for the same data.
        idx = next(
            (i for i, c in enumerate(session.document.children) if c.id == self.page_id),
            None
        )
        if idx is None:
            raise ValueError(f"Page with ID {self.page_id} not found.")

        self.original_index = idx
        self.deleted_page = session.document.children[idx]
        # Rebuild the list without the deleted page
        session.document.children = [
            c for c in session.document.children if c.id != self.page_id
        ]

    def undo(self, session: EditorSession) -> None:
        if self.deleted_page is not None and self.original_index != -1:
            children = list(session.document.children)
            children.insert(self.original_index, self.deleted_page)
            session.document.children = children


class MovePageCommand(Command):
    """Moves a page to a new index in the document."""
    def __init__(self, page_id: str, new_index: int):
        self.page_id = page_id
        self.new_index = new_index
        self.old_index = -1

    def execute(self, session: EditorSession) -> None:
        # Find index by ID — never use list.index(obj) with Pydantic models
        idx = next(
            (i for i, c in enumerate(session.document.children) if c.id == self.page_id),
            None
        )
        if idx is None:
            raise ValueError(f"Page with ID {self.page_id} not found.")

        self.old_index = idx
        page = session.document.children[idx]

        children = [c for c in session.document.children if c.id != self.page_id]
        target = max(0, min(self.new_index, len(children)))
        children.insert(target, page)
        session.document.children = children

    def undo(self, session: EditorSession) -> None:
        if self.old_index == -1:
            return
        idx = next(
            (i for i, c in enumerate(session.document.children) if c.id == self.page_id),
            None
        )
        if idx is None:
            return
        page = session.document.children[idx]
        children = [c for c in session.document.children if c.id != self.page_id]
        children.insert(self.old_index, page)
        session.document.children = children