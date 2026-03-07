from engine.src.editor.editor_session import EditorSession
from engine.src.core.annotation_nodes import TextNode, ImageNode, HighlightNode
from engine.src.core.node import BoundingBox
from engine.src.commands.node_commands import AddNodeCommand, DeleteNodeCommand

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
                      width: float, height: float, color: str = "#FFFF00") -> HighlightNode:
        """Creates a HighlightNode and executes the command."""
        highlight_node = HighlightNode(
            color=color,
            bbox=BoundingBox(x=x, y=y, width=width, height=height)
        )
        
        command = AddNodeCommand(parent_id=page_id, new_node=highlight_node)
        self.session.execute(command)
        return highlight_node

    def delete_annotation(self, node_id: str) -> None:
        """Removes an annotation by its ID."""
        command = DeleteNodeCommand(node_id=node_id)
        self.session.execute(command)