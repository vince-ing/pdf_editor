from abc import ABC, abstractmethod

class Command(ABC):
    """
    Abstract base class for all PDF operations.
    Enables the Command Pattern for future undo/redo, macros, and GUI integration.
    """
    
    @abstractmethod
    def execute(self):
        """Executes the command logic."""
        pass

    @abstractmethod
    def undo(self):
        """
        Reverses the command logic.
        Requires implementation, even if it's a no-op or state-reversion warning.
        """
        pass