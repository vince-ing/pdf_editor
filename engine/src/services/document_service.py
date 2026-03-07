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

        for page_num in range(len(doc)):
            fitz_page = doc[page_num]
            page_node = PageNode(
                page_number=page_num,
                rotation=fitz_page.rotation
            )
            rect = fitz_page.rect
            page_node.metadata["width"] = rect.width
            page_node.metadata["height"] = rect.height
            document_node.add_page(page_node)

        doc.close()

        self.session.document = document_node
        self.session.undo_stack.clear()
        self.session.redo_stack.clear()

        return document_node

    def export_document(self, output_path: str) -> str:
        """
        Flattens the Scene Graph back into a physical PDF file.

        Correctly handles:
        - Page deletion (only pages still in the scene graph are included)
        - Page reordering (pages are written in scene graph order)
        - Rotation (applied per page from scene graph state)
        - Annotations (text boxes and highlights)
        """
        original_path = self.session.document.file_path

        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError("Original PDF not found. Cannot export.")

        src = fitz.open(original_path)
        out = fitz.open()

        for page_node in self.session.document.pages:
            # Copy the source page (by original page_number) into the output doc
            src_page_index = page_node.page_number
            if src_page_index < 0 or src_page_index >= len(src):
                continue  # skip if somehow out of range

            out.insert_pdf(src, from_page=src_page_index, to_page=src_page_index)
            out_page = out[-1]  # the page we just inserted

            # Apply rotation from scene graph
            if out_page.rotation != page_node.rotation:
                out_page.set_rotation(page_node.rotation)

            # Apply annotations
            for child in page_node.get_annotations():
                if isinstance(child, TextNode) and child.bbox:
                    rgb = self._hex_to_rgb(child.color)
                    rect = fitz.Rect(
                        child.bbox.x,
                        child.bbox.y,
                        child.bbox.x + child.bbox.width,
                        child.bbox.y + child.bbox.height
                    )
                    out_page.insert_textbox(
                        rect,
                        child.text_content,
                        fontsize=child.font_size,
                        fontname="helv",
                        color=rgb
                    )

                elif isinstance(child, HighlightNode) and child.bbox:
                    rect = fitz.Rect(
                        child.bbox.x,
                        child.bbox.y,
                        child.bbox.x + child.bbox.width,
                        child.bbox.y + child.bbox.height
                    )
                    annot = out_page.add_highlight_annot(rect)
                    annot.set_colors(stroke=self._hex_to_rgb(child.color))
                    annot.set_opacity(child.opacity)
                    annot.update()

        src.close()
        out.save(output_path)
        out.close()
        return output_path

    def export_to_bytes(self) -> bytes:
        """
        Same as export_document but returns the PDF as bytes (for HTTP streaming).
        """
        original_path = self.session.document.file_path
        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError("Original PDF not found. Cannot export.")

        src = fitz.open(original_path)
        out = fitz.open()

        for page_node in self.session.document.pages:
            src_page_index = page_node.page_number
            if src_page_index < 0 or src_page_index >= len(src):
                continue

            out.insert_pdf(src, from_page=src_page_index, to_page=src_page_index)
            out_page = out[-1]

            if out_page.rotation != page_node.rotation:
                out_page.set_rotation(page_node.rotation)

            for child in page_node.get_annotations():
                if isinstance(child, TextNode) and child.bbox:
                    rgb = self._hex_to_rgb(child.color)
                    rect = fitz.Rect(
                        child.bbox.x,
                        child.bbox.y,
                        child.bbox.x + child.bbox.width,
                        child.bbox.y + child.bbox.height
                    )
                    out_page.insert_textbox(
                        rect,
                        child.text_content,
                        fontsize=child.font_size,
                        fontname="helv",
                        color=rgb
                    )

                elif isinstance(child, HighlightNode) and child.bbox:
                    rect = fitz.Rect(
                        child.bbox.x,
                        child.bbox.y,
                        child.bbox.x + child.bbox.width,
                        child.bbox.y + child.bbox.height
                    )
                    annot = out_page.add_highlight_annot(rect)
                    annot.set_colors(stroke=self._hex_to_rgb(child.color))
                    annot.set_opacity(child.opacity)
                    annot.update()

        src.close()
        pdf_bytes = out.tobytes()
        out.close()
        return pdf_bytes

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (0, 0, 0)
        return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))