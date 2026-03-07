from typing import Optional
from pydantic import Field
from .node import Node, BoundingBox

class PageNode(Node):
    """Represents a single page within a Document."""
    node_type: str = "page"
    page_number: int
    rotation: int = 0
    # The rendered background image or original PDF page reference
    source_reference: Optional[str] = None 

    def get_annotations(self) -> list[Node]:
        """Returns all child nodes that are not structural (e.g., text, highlights)."""
        # We can expand this logic as we add AnnotationNode classes
        return [child for child in self.children if child.node_type not in ("group", "layer")]