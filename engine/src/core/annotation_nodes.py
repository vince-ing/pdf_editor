# engine/src/core/annotation_nodes.py

from typing import Optional, List, Tuple
from pydantic import BaseModel, Field
from .node import Node

class TextRun(BaseModel):
    """
    A contiguous span of text sharing the same style within a TextNode.
    When a TextNode has runs, they take precedence over the top-level style
    fields (font_family, font_size, color, bold, italic) for rendering.
    The top-level fields serve as defaults for any run that omits a property.
    """
    text:        str
    bold:        bool  = False
    italic:      bool  = False
    font_family: str   = "Helvetica"
    font_size:   float = 12.0
    color:       str   = "#000000"


class TextNode(Node):
    """Represents a styled text box added to a page."""
    node_type:    str   = "text"
    text_content: str   = ""          # flat fallback / plain-text summary
    font_family:  str   = "Helvetica"
    font_size:    float = 12.0
    color:        str   = "#000000"
    bold:         bool  = False
    italic:       bool  = False
    # Rich-text runs. When present, rendering uses these instead of the
    # flat fields above.  An empty list means "use flat fields".
    runs: List[TextRun] = Field(default_factory=list)


class ImageNode(Node):
    """Represents an image inserted onto a page."""
    node_type:    str            = "image"
    image_path:   Optional[str] = None
    image_base64: Optional[str] = None
    opacity:      float          = 1.0


class HighlightNode(Node):
    """Represents a highlighted area on a page."""
    node_type:    str   = "highlight"
    color:        str   = "#FFFF00"
    opacity:      float = 0.5
    border_width: float = 0.0

class Point(BaseModel):
    x: float
    y: float

class PathNode(Node):
    """Represents a freehand drawing path added to a page."""
    node_type:    str   = "path"
    points:       List[Point] = Field(default_factory=list)
    color:        str   = "#000000"
    thickness:    float = 2.0
    opacity:      float = 1.0