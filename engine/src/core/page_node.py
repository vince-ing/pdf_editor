from typing import Optional
from pydantic import Field
from .node import Node, BoundingBox

class CropBox(BoundingBox):
    """Crop region in PDF coordinate space (origin = bottom-left, y increases upward)."""
    pass

class PageNode(Node):
    """Represents a single page within a Document."""
    node_type: str = "page"
    page_number: int
    rotation: int = 0
    source_reference: Optional[str] = None
    crop_box: Optional[CropBox] = None  # None = no crop (full page)

    def get_annotations(self) -> list[Node]:
        """Returns all child nodes that are not structural (e.g., text, highlights)."""
        return [child for child in self.children if child.node_type not in ("group", "layer")]