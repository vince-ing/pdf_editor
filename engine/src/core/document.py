from pydantic import Field
from typing import Optional
from .node import Node
from .page_node import PageNode

class DocumentNode(Node):
    """The root node representing the entire PDF document."""
    node_type: str = "document"
    file_path: Optional[str] = None
    file_name: str = "Untitled.pdf"
    
    def add_page(self, page: PageNode) -> None:
        self.add_child(page)

    def get_page(self, page_number: int) -> Optional[PageNode]:
        for child in self.children:
            if isinstance(child, PageNode) and child.page_number == page_number:
                return child
        return None

    @property
    def pages(self) -> list[PageNode]:
        return [child for child in self.children if isinstance(child, PageNode)]