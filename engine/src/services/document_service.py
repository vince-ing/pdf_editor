import os
import fitz  # PyMuPDF
from typing import Optional

from engine.src.editor.editor_session import EditorSession
from engine.src.core.document import DocumentNode
from engine.src.core.page_node import PageNode
from engine.src.core.annotation_nodes import TextNode, HighlightNode

class DocumentService:
    """
    Handles file I/O operations: loading physical PDFs into the Scene Graph
    and exporting the Scene Graph back to a physical PDF.
    """
    def __init__(self, session: EditorSession):
        self.session = session

    def load_document(self, file_path: str) -> DocumentNode:
        """Parses a physical PDF and initializes the Pydantic document tree."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        doc = fitz.open(file_path)
        document_node = DocumentNode(
            file_path=file_path, 
            file_name=os.path.basename(file_path)
        )

        # Parse pages
        for page_num in range(len(doc)):
            fitz_page = doc[page_num]
            
            page_node = PageNode(
                page_number=page_num,
                rotation=fitz_page.rotation
            )
            # Store page dimensions in metadata if needed for frontend aspect ratios
            rect = fitz_page.rect
            page_node.metadata["width"] = rect.width
            page_node.metadata["height"] = rect.height
            
            document_node.add_page(page_node)
        
        doc.close()
        
        # Replace the current session document
        self.session.document = document_node
        self.session.undo_stack.clear()
        self.session.redo_stack.clear()
        
        return document_node

    def export_document(self, output_path: str) -> str:
        """Flattens the Scene Graph back into a physical PDF file."""
        original_path = self.session.document.file_path
        
        # Open original file to act as the base layer, or create new if empty
        if original_path and os.path.exists(original_path):
            doc = fitz.open(original_path)
        else:
            doc = fitz.open()

        # Iterate through our Scene Graph pages
        for page_node in self.session.document.pages:
            # Ensure the physical document has this page (if it was added dynamically)
            while len(doc) <= page_node.page_number:
                doc.new_page()
            
            fitz_page = doc[page_node.page_number]
            
            # Apply state changes: Rotation
            if fitz_page.rotation != page_node.rotation:
                fitz_page.set_rotation(page_node.rotation)

            # Apply state changes: Annotations
            for child in page_node.get_annotations():
                if isinstance(child, TextNode) and child.bbox:
                    # Convert our hex color back to an RGB tuple (0-1 range for fitz)
                    rgb = self._hex_to_rgb(child.color)
                    rect = fitz.Rect(
                        child.bbox.x, 
                        child.bbox.y, 
                        child.bbox.x + child.bbox.width, 
                        child.bbox.y + child.bbox.height
                    )
                    fitz_page.insert_textbox(
                        rect, 
                        child.text_content, 
                        fontsize=child.font_size, 
                        fontname="helv", # Map to standard fonts or load custom
                        color=rgb
                    )
                
                elif isinstance(child, HighlightNode) and child.bbox:
                    rect = fitz.Rect(
                        child.bbox.x, 
                        child.bbox.y, 
                        child.bbox.x + child.bbox.width, 
                        child.bbox.y + child.bbox.height
                    )
                    annot = fitz_page.add_highlight_annot(rect)
                    annot.set_colors(stroke=self._hex_to_rgb(child.color))
                    annot.set_opacity(child.opacity)
                    annot.update()

        doc.save(output_path)
        doc.close()
        return output_path

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        """Helper to convert #RRGGBB to PyMuPDF's expected (r, g, b) tuple mapped 0.0 to 1.0."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (0, 0, 0)
        return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))