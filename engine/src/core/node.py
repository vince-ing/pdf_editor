import uuid
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float

class Node(BaseModel):
    """Base class for all elements in the document scene graph."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: str = "base_node"
    parent_id: Optional[str] = None
    children: List['Node'] = Field(default_factory=list)
    bbox: Optional[BoundingBox] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def add_child(self, child: 'Node') -> None:
        child.parent_id = self.id
        self.children.append(child)

    def remove_child(self, child_id: str) -> bool:
        original_length = len(self.children)
        self.children = [c for c in self.children if c.id != child_id]
        return len(self.children) < original_length

    def get_child(self, child_id: str) -> Optional['Node']:
        for child in self.children:
            if child.id == child_id:
                return child
            # Recursive search if nodes are nested deeply
            found = child.get_child(child_id)
            if found:
                return found
        return None

# Required for recursive type references in Pydantic models
Node.model_rebuild()