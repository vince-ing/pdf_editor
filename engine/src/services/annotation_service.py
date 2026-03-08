# engine/src/services/annotation_service.py

from typing import List
from engine.src.editor.editor_session import EditorSession
from engine.src.core.annotation_nodes import TextNode, ImageNode, HighlightNode
from engine.src.core.node import BoundingBox
from engine.src.commands.node_commands import AddNodeCommand, DeleteNodeCommand, BatchAddNodeCommand

class AnnotationService:
    """
    Coordinates annotation operations.
    The API layer calls these methods rather than interacting with commands directly.
    """
    def __init__(self, session: EditorSession):
        self.session = session

    def add_text(self, page_id: str, text: str, x: float, y: float, 
                 width: float = 100, height: float = 50, **kwargs) -> TextNode:
        """Creates a TextNode and executes the command to add it to the page."""
        text_node = TextNode(
            text_content=text,
            bbox=BoundingBox(x=x, y=y, width=width, height=height),
            **kwargs
        )
        
        command = AddNodeCommand(parent_id=page_id, new_node=text_node)
        self.session.execute(command)
        return text_node

    def add_highlight(self, page_id: str, x: float, y: float, 
                      width: float, height: float, color: str = "#FFFF00",
                      border_width: float = 0.0, opacity: float = 0.5, **kwargs) -> HighlightNode:
        """Creates a single HighlightNode and executes the command."""
        highlight_node = HighlightNode(
            color=color,
            bbox=BoundingBox(x=x, y=y, width=width, height=height),
            border_width=border_width,
            opacity=opacity,
            **kwargs
        )
        
        command = AddNodeCommand(parent_id=page_id, new_node=highlight_node)
        self.session.execute(command)
        return highlight_node

    def add_highlights(self, page_id: str, rects: List[dict], color: str = "#FFFF00",
                       border_width: float = 0.0, opacity: float = 0.5, **kwargs) -> List[HighlightNode]:
        """Creates multiple HighlightNodes and executes them as a single command for proper undo grouping."""
        nodes = []
        for rect in rects:
            nodes.append(HighlightNode(
                color=color,
                bbox=BoundingBox(x=rect["x"], y=rect["y"], width=rect["width"], height=rect["height"]),
                border_width=border_width,
                opacity=opacity,
                **kwargs
            ))
            
        command = BatchAddNodeCommand(parent_id=page_id, new_nodes=nodes)
        self.session.execute(command)
        return nodes

    def delete_annotation(self, node_id: str) -> None:
        """Removes an annotation by its ID."""
        command = DeleteNodeCommand(node_id=node_id)
        self.session.execute(command)