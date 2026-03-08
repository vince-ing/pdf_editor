import os
import fitz
from typing import Optional
from engine.src.editor.editor_session import EditorSession
from engine.src.core.page_node import PageNode
from engine.src.commands.node_commands import AddNodeCommand
from engine.src.commands.page_commands import RotatePageCommand, DeletePageCommand, MovePageCommand, CropPageCommand

class PageService:
    """
    Coordinates page-level operations for the API.
    All mutations go through self.session.execute() so the undo stack is maintained.
    """
    def __init__(self, session: EditorSession):
        self.session = session

    def add_page(self, page_number: int, source_ref: Optional[str] = None) -> PageNode:
        """Creates a new page node and appends it to the document root."""
        page = PageNode(page_number=page_number, source_reference=source_ref)
        command = AddNodeCommand(parent_id=self.session.document.id, new_node=page)
        self.session.execute(command)
        return page

    def rotate_page(self, page_id: str, degrees: int = 90) -> PageNode:
        """Executes a rotation command and returns the updated page."""
        command = RotatePageCommand(page_id=page_id, degrees=degrees)
        self.session.execute(command)
        return self.session.document.get_child(page_id)

    def delete_page(self, page_id: str) -> bool:
        """Deletes a page via the session so it lands on the undo stack."""
        command = DeletePageCommand(page_id)
        self.session.execute(command)
        return True

    def move_page(self, page_id: str, new_index: int) -> bool:
        """Moves a page to new_index via the session so it lands on the undo stack."""
        command = MovePageCommand(page_id, new_index)
        self.session.execute(command)
        return True

    def crop_page(self, page_id: str, x: float, y: float, width: float, height: float) -> bool:
        """Crops a page to the given rectangle via the undo stack."""
        command = CropPageCommand(page_id, x, y, width, height)
        self.session.execute(command)
        return True

    def get_page_chars(self, page_id: str) -> list:
        """Extracts character-level bounding boxes for text selection."""
        page_node = self.session.document.get_child(page_id)
        if not page_node:
            raise ValueError(f"Page {page_id} not found.")

        file_path = self.session.document.file_path
        if not file_path or not os.path.exists(file_path):
            return []

        doc = fitz.open(file_path)
        try:
            src_page_index = page_node.page_number
            if src_page_index < 0 or src_page_index >= len(doc):
                return []
            
            fitz_page = doc[src_page_index]
            
            # "rawdict" provides deep text structure down to the individual character
            rawdict = fitz_page.get_text("rawdict")
            
            chars = []
            for block in rawdict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        for char in span.get("chars", []):
                            bbox = char.get("bbox")
                            if bbox and len(bbox) == 4:
                                chars.append({
                                    "text": char.get("c", ""),
                                    "x": bbox[0],
                                    "y": bbox[1],
                                    "width": bbox[2] - bbox[0],
                                    "height": bbox[3] - bbox[1],
                                    "bbox": bbox  # Expose the raw array for the frontend
                                })
            return chars
        finally:
            doc.close()