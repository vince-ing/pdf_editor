# engine/src/commands/node_commands.py

from typing import Optional, List
from .base import Command
from engine.src.core.node import Node
from engine.src.editor.editor_session import EditorSession

class AddNodeCommand(Command):
    """Adds a single node to a specific parent node in the document."""
    def __init__(self, parent_id: str, new_node: Node):
        self.parent_id = parent_id
        self.new_node = new_node

    def execute(self, session: EditorSession) -> None:
        self.new_node.parent_id = self.parent_id 
        
        if session.document.id == self.parent_id:
            session.document.add_child(self.new_node)
            return

        parent = session.document.get_child(self.parent_id)
        if parent:
            parent.add_child(self.new_node)
        else:
            raise ValueError(f"Parent node with ID {self.parent_id} not found.")

    def undo(self, session: EditorSession) -> None:
        if session.document.id == self.parent_id:
            session.document.remove_child(self.new_node.id)
            return

        parent = session.document.get_child(self.parent_id)
        if parent:
            parent.remove_child(self.new_node.id)


class BatchAddNodeCommand(Command):
    """Adds multiple nodes to a specific parent node in a single action (useful for multi-line highlights)."""
    def __init__(self, parent_id: str, new_nodes: List[Node]):
        self.parent_id = parent_id
        self.new_nodes = new_nodes

    def execute(self, session: EditorSession) -> None:
        for node in self.new_nodes:
            node.parent_id = self.parent_id 
            
        if session.document.id == self.parent_id:
            for node in self.new_nodes:
                session.document.add_child(node)
            return

        parent = session.document.get_child(self.parent_id)
        if parent:
            for node in self.new_nodes:
                parent.add_child(node)
        else:
            raise ValueError(f"Parent node with ID {self.parent_id} not found.")

    def undo(self, session: EditorSession) -> None:
        if session.document.id == self.parent_id:
            for node in self.new_nodes:
                session.document.remove_child(node.id)
            return

        parent = session.document.get_child(self.parent_id)
        if parent:
            for node in self.new_nodes:
                parent.remove_child(node.id)


class DeleteNodeCommand(Command):
    """Deletes a node from the document and stores it for potential undo."""
    def __init__(self, node_id: str):
        self.node_id = node_id
        self._deleted_node: Optional[Node] = None
        self._parent_id: Optional[str] = None

    def execute(self, session: EditorSession) -> None:
        target_node = session.document.get_child(self.node_id)
        if not target_node:
            raise ValueError(f"Node with ID {self.node_id} not found.")

        self._deleted_node = target_node
        self._parent_id = target_node.parent_id

        if self._parent_id == session.document.id:
            session.document.remove_child(self.node_id)
        else:
            parent = session.document.get_child(self._parent_id)
            if parent:
                parent.remove_child(self.node_id)

    def undo(self, session: EditorSession) -> None:
        if not self._deleted_node or not self._parent_id:
            return

        if self._parent_id == session.document.id:
            session.document.add_child(self._deleted_node)
        else:
            parent = session.document.get_child(self._parent_id)
            if parent:
                parent.add_child(self._deleted_node)