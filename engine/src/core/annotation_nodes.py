from typing import Optional
from pydantic import Field
from .node import Node

class TextNode(Node):
    """Represents a text box added to a page."""
    node_type: str = "text"
    text_content: str
    font_family: str = "Helvetica"
    font_size: float = 12.0
    color: str = "#000000"  # Hex color

class ImageNode(Node):
    """Represents an image inserted onto a page."""
    node_type: str = "image"
    image_path: Optional[str] = None
    image_base64: Optional[str] = None  # Useful for web/mobile payloads
    opacity: float = 1.0

class HighlightNode(Node):
    """Represents a highlighted area on a page."""
    node_type: str = "highlight"
    color: str = "#FFFF00"
    opacity: float = 0.5