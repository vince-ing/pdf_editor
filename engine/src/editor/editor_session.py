from typing import List, Optional
from engine.src.core.document import DocumentNode
from engine.src.commands.base import Command

class EditorSession:
    """
    Manages the current document state and the execution/history of commands.
    This acts as the central hub for the headless engine.
    """
    def __init__(self, document: Optional[DocumentNode] = None):
        self.document = document or DocumentNode()
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []

    def execute(self, command: Command) -> None:
        """Executes a command and adds it to the undo history."""
        command.execute(self)
        self.undo_stack.append(command)
        self.redo_stack.clear()

    def undo(self) -> bool:
        """Undoes the last command. Returns True if successful."""
        if not self.undo_stack:
            return False
        
        cmd = self.undo_stack.pop()
        cmd.undo(self)
        self.redo_stack.append(cmd)
        return True

    def redo(self) -> bool:
        """Redoes the last undone command. Returns True if successful."""
        if not self.redo_stack:
            return False
            
        cmd = self.redo_stack.pop()
        cmd.execute(self)
        self.undo_stack.append(cmd)
        return True