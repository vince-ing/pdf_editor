# engine/src/services/document_service.py

import os
import fitz  # PyMuPDF
from typing import Optional

from engine.src.editor.editor_session import EditorSession
from engine.src.core.document import DocumentNode
from engine.src.core.page_node import PageNode
from engine.src.core.annotation_nodes import TextNode, HighlightNode

# Maps our UI font name + bold/italic → fitz built-in font name.
_FITZ_FONT: dict[tuple[str, bool, bool], str] = {
    ("Helvetica",       False, False): "helv",
    ("Helvetica",       True,  False): "hebo",
    ("Helvetica",       False, True ): "heit",
    ("Helvetica",       True,  True ): "hebi",
    ("Times New Roman", False, False): "tiro",
    ("Times New Roman", True,  False): "tibo",
    ("Times New Roman", False, True ): "tiit",
    ("Times New Roman", True,  True ): "tibi",
    ("Courier",         False, False): "cour",
    ("Courier",         True,  False): "cobo",
    ("Courier",         False, True ): "coit",
    ("Courier",         True,  True ): "cobi",
}


def _fitz_font(family: str, bold: bool, italic: bool) -> str:
    return _FITZ_FONT.get((family, bold, italic), "helv")


class DocumentService:
    def __init__(self, session: EditorSession):
        self.session = session

    def load_document(self, file_path: str) -> DocumentNode:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        doc = fitz.open(file_path)
        document_node = DocumentNode(
            file_path=file_path,
            file_name=os.path.basename(file_path),
        )

        for page_num in range(len(doc)):
            fitz_page = doc[page_num]
            page_node = PageNode(page_number=page_num, rotation=fitz_page.rotation)
            rect = fitz_page.rect
            page_node.metadata["width"]  = rect.width
            page_node.metadata["height"] = rect.height
            document_node.add_page(page_node)

        doc.close()
        self.session.document = document_node
        self.session.undo_stack.clear()
        self.session.redo_stack.clear()
        return document_node

    # ── Export helpers ─────────────────────────────────────────────────────────

    def _render_text_node(self, out_page: fitz.Page, node: TextNode) -> None:
        if not node.bbox:
            return

        bbox = node.bbox
        clip = fitz.Rect(bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)

        if not node.runs:
            fontname = _fitz_font(node.font_family, node.bold, node.italic)
            out_page.insert_textbox(
                clip,
                node.text_content,
                fontsize=node.font_size,
                fontname=fontname,
                color=self._hex_to_rgb(node.color),
            )
            return

        line_height_multiplier = 1.2
        x0    = bbox.x
        y0    = bbox.y
        max_x = bbox.x + bbox.width
        max_y = bbox.y + bbox.height

        cursor_x = x0
        first_run_size = node.runs[0].font_size if node.runs else node.font_size
        cursor_y = y0 + first_run_size  

        for run in node.runs:
            fontname = _fitz_font(run.font_family, run.bold, run.italic)
            fs       = run.font_size
            rgb      = self._hex_to_rgb(run.color)
            lh       = fs * line_height_multiplier

            segments = run.text.split('\n')
            for seg_idx, segment in enumerate(segments):
                if seg_idx > 0:
                    cursor_x  = x0
                    cursor_y += lh
                    if cursor_y > max_y:
                        return

                words = segment.split(' ')
                for w_idx, word in enumerate(words):
                    piece = ('' if w_idx == 0 and cursor_x == x0 else ' ') + word
                    piece_w = len(piece) * fs * 0.6

                    if cursor_x + piece_w > max_x and cursor_x > x0:
                        cursor_x  = x0
                        cursor_y += lh
                        if cursor_y > max_y:
                            return
                        piece = word 

                    if cursor_x + len(piece) * fs * 0.6 > max_x + fs:
                        pass

                    out_page.insert_text(
                        fitz.Point(cursor_x, cursor_y),
                        piece,
                        fontsize=fs,
                        fontname=fontname,
                        color=rgb,
                    )
                    cursor_x += len(piece) * fs * 0.6

    # ── Public export API ──────────────────────────────────────────────────────

    def export_document(self, output_path: str) -> str:
        out = self._build_output_doc()
        out.save(output_path, garbage=4, deflate=True)
        out.close()
        return output_path

    def export_to_bytes(self) -> bytes:
        out = self._build_output_doc()
        pdf_bytes = out.tobytes(garbage=4, deflate=True)
        out.close()
        return pdf_bytes

    def _build_output_doc(self):
        original_path = self.session.document.file_path
        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError("Original PDF not found. Cannot export.")

        out = fitz.open(original_path)

        desired_page_numbers = []
        for page_node in self.session.document.pages:
            if 0 <= page_node.page_number < len(out):
                desired_page_numbers.append(page_node.page_number)
        
        out.select(desired_page_numbers)

        for i, page_node in enumerate(self.session.document.pages):
            out_page = out[i]

            # 1. Apply Redactions first
            has_redactions = False
            other_annots = []

            for child in page_node.get_annotations():
                if isinstance(child, HighlightNode) and child.color == "#000000" and child.opacity == 1.0 and child.bbox:
                    rect = fitz.Rect(child.bbox.x, child.bbox.y, child.bbox.x + child.bbox.width, child.bbox.y + child.bbox.height)
                    out_page.add_redact_annot(rect, fill=(0.0, 0.0, 0.0))
                    has_redactions = True
                else:
                    other_annots.append(child)

            if has_redactions:
                # FIX: Set images=0 and graphics=0 to prevent apply_redactions() from 
                # destroying underlying clipping paths or vector backgrounds. 
                # If a page's global clipping path is accidentally redacted, all other 
                # text on the page goes invisible but remains physically selectable.
                out_page.apply_redactions(images=0, graphics=0)

            # 2. Apply page transformations (rotation, crop)
            if out_page.rotation != page_node.rotation:
                out_page.set_rotation(page_node.rotation)

            if page_node.crop_box:
                cb = page_node.crop_box
                crop_rect = fitz.Rect(cb.x, cb.y, cb.x + cb.width, cb.y + cb.height)
                out_page.set_cropbox(crop_rect)

            # 3. Apply standard annotations (Text, Highlight)
            for child in other_annots:
                if isinstance(child, TextNode) and child.bbox:
                    self._render_text_node(out_page, child)
                elif isinstance(child, HighlightNode) and child.bbox:
                    rect = fitz.Rect(child.bbox.x, child.bbox.y, child.bbox.x + child.bbox.width, child.bbox.y + child.bbox.height)
                    annot = out_page.add_highlight_annot(rect)
                    annot.set_colors(stroke=self._hex_to_rgb(child.color))
                    annot.set_opacity(child.opacity)
                    annot.update()

        return out

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (0, 0, 0)
        return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))