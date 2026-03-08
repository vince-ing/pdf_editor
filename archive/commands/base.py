from abc import ABC, abstractmethod


class Command(ABC):
    """
    Abstract base class for all PDF operations.
    Enables the Command Pattern for undo/redo, macros, and GUI integration.
    """

    @abstractmethod
    def execute(self) -> None:
        """Executes the command logic."""
        pass

    @abstractmethod
    def undo(self) -> None:
        """Reverses the command logic."""
        pass

    def cleanup(self) -> None:
        """
        Release any resources held by this command (e.g. temp snapshot files).
        Called by the history manager when this command is permanently discarded
        — either because a new action truncated forward history, or because the
        document was closed / the app exited.
        Default implementation is a no-op; override in commands that allocate
        external resources.
        """
        pass