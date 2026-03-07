from typing import Dict, Type
from fastapi import FastAPI, APIRouter
from engine.src.editor.editor_session import EditorSession
from .plugin import Plugin

class PluginManager:
    """
    Manages the lifecycle and routing for all registered plugins.
    """
    def __init__(self, app: FastAPI, session: EditorSession):
        self.app = app
        self.session = session
        self.plugins: Dict[str, Plugin] = {}
        # All plugins will be grouped under this prefix
        self.router = APIRouter(prefix="/api/plugins", tags=["Plugins"])

    def register_plugin(self, plugin_class: Type[Plugin]) -> None:
        """Instantiates a plugin and registers its routes."""
        plugin_instance = plugin_class()
        
        # Create a sub-router specifically for this plugin to avoid route collisions
        plugin_router = APIRouter(prefix=f"/{plugin_instance.name.lower()}")
        
        # Let the plugin attach its endpoints to its sub-router
        plugin_instance.register_routes(plugin_router, self.session)
        
        # Attach the plugin's sub-router to the main plugin router
        self.router.include_router(plugin_router)
        self.plugins[plugin_instance.name] = plugin_instance
        print(f"Registered Plugin: {plugin_instance.name} v{plugin_instance.version}")

    def finalize(self) -> None:
        """Mounts the accumulated plugin routes to the main FastAPI app."""
        self.app.include_router(self.router)