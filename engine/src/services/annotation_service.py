# engine/src/services/annotation_service.py

from typing import List, Optional
from engine.src.editor.editor_session import EditorSession
from engine.src.core.annotation_nodes import TextNode, TextRun, ImageNode, HighlightNode
from engine.src.core.node import BoundingBox
from engine.src.commands.node_commands import AddNodeCommand, DeleteNodeCommand, BatchAddNodeCommand


class AnnotationService:
    def __init__(self, session: EditorSession):
        self.session = session

    def add_text(
        self,
        page_id:     str,
        text:        str,
        x:           float,
        y:           float,
        width:       float = 100,
        height:      float = 50,
        font_family: str   = "Helvetica",
        font_size:   float = 12.0,
        color:       str   = "#000000",
        bold:        bool  = False,
        italic:      bool  = False,
        runs:        Optional[List[dict]] = None,
        **kwargs,
    ) -> TextNode:
        run_objects = [TextRun(**r) for r in (runs or [])]

        text_node = TextNode(
            text_content=text,
            bbox=BoundingBox(x=x, y=y, width=width, height=height),
            font_family=font_family,
            font_size=font_size,
            color=color,
            bold=bold,
            italic=italic,
            runs=run_objects,
        )
        command = AddNodeCommand(parent_id=page_id, new_node=text_node)
        self.session.execute(command)
        return text_node

    def add_highlight(
        self,
        page_id:      str,
        x:            float,
        y:            float,
        width:        float,
        height:       float,
        color:        str   = "#FFFF00",
        border_width: float = 0.0,
        opacity:      float = 0.5,
        **kwargs,
    ) -> HighlightNode:
        highlight_node = HighlightNode(
            color=color,
            bbox=BoundingBox(x=x, y=y, width=width, height=height),
            border_width=border_width,
            opacity=opacity,
        )
        command = AddNodeCommand(parent_id=page_id, new_node=highlight_node)
        self.session.execute(command)
        return highlight_node

    def add_highlights(
        self,
        page_id:      str,
        rects:        List[dict],
        color:        str   = "#FFFF00",
        border_width: float = 0.0,
        opacity:      float = 0.5,
        **kwargs,
    ) -> List[HighlightNode]:
        nodes = [
            HighlightNode(
                color=color,
                bbox=BoundingBox(x=r["x"], y=r["y"], width=r["width"], height=r["height"]),
                border_width=border_width,
                opacity=opacity,
            )
            for r in rects
        ]
        command = BatchAddNodeCommand(parent_id=page_id, new_nodes=nodes)
        self.session.execute(command)
        return nodes

    def update_annotation(self, page_id: str, node_id: str, updates: dict):
        from engine.src.commands.node_commands import UpdateAnnotationCommand

        # If runs are being updated, convert them from dicts → TextRun objects
        if "runs" in updates and updates["runs"] is not None:
            updates["runs"] = [
                TextRun(**r) if isinstance(r, dict) else r
                for r in updates["runs"]
            ]

        cmd = UpdateAnnotationCommand(page_id, node_id, updates)
        self.session.execute(cmd)

        page = self.session.document.get_child(page_id)
        return page.get_child(node_id)

    def delete_annotation(self, node_id: str) -> None:
        command = DeleteNodeCommand(node_id=node_id)
        self.session.execute(command)