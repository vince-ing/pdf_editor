from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from editor.editor_session import EditorSession

class Command(ABC):
    """
    Abstract base class for all engine commands.
    Commands encapsulate an atomic change to the document scene graph.
    """
    
    @abstractmethod
    def execute(self, session: 'EditorSession') -> None:
        """Applies the change to the document."""
        pass

    @abstractmethod
    def undo(self, session: 'EditorSession') -> None:
        """Reverts the change from the document."""
        pass