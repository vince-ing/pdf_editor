from abc import ABC, abstractmethod
from fastapi import APIRouter
from engine.src.editor.editor_session import EditorSession

class Plugin(ABC):
    """
    Abstract base class for engine plugins.
    Each plugin defines its own FastAPI routes and logic.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """The unique name of the plugin."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """The current version of the plugin."""
        pass

    @abstractmethod
    def register_routes(self, router: APIRouter, session: EditorSession) -> None:
        """
        Registers the plugin's specific endpoints to the provided APIRouter.
        The session is passed so the plugin can mutate the Scene Graph.
        """
        pass