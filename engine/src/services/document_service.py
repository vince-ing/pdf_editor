# engine/src/services/document_service.py

import os
import fitz  # PyMuPDF
from typing import Optional

from engine.src.editor.editor_session import EditorSession
from engine.src.core.document import DocumentNode
from engine.src.core.page_node import PageNode
from engine.src.core.annotation_nodes import TextNode, HighlightNode

# Maps our UI font name + bold/italic → fitz built-in font name.
# PyMuPDF built-in font names: helv, hebo, heit, hebi, tiro, tiit, tibi, tibo, cour, cobi, cobo, coit
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

    def _apply_annotations(self, out_page: fitz.Page, page_node: PageNode) -> None:
        """Write all annotations from a PageNode onto a fitz page."""
        for child in page_node.get_annotations():

            if isinstance(child, TextNode) and child.bbox:
                self._render_text_node(out_page, child)

            elif isinstance(child, HighlightNode) and child.bbox:
                rect  = fitz.Rect(child.bbox.x, child.bbox.y,
                                  child.bbox.x + child.bbox.width,
                                  child.bbox.y + child.bbox.height)
                annot = out_page.add_highlight_annot(rect)
                annot.set_colors(stroke=self._hex_to_rgb(child.color))
                annot.set_opacity(child.opacity)
                annot.update()

    def _render_text_node(self, out_page: fitz.Page, node: TextNode) -> None:
        """
        Render a TextNode onto a fitz page.

        If the node has `runs` we walk each run and call insert_text with the
        correct position, advancing the cursor manually.
        If there are no runs we fall back to insert_textbox (single style).
        """
        if not node.bbox:
            return

        bbox = node.bbox
        clip = fitz.Rect(bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)

        if not node.runs:
            # ── Flat / single-style ──────────────────────────────────────────
            fontname = _fitz_font(node.font_family, node.bold, node.italic)
            out_page.insert_textbox(
                clip,
                node.text_content,
                fontsize=node.font_size,
                fontname=fontname,
                color=self._hex_to_rgb(node.color),
            )
            return

        # ── Rich-text runs ───────────────────────────────────────────────────
        # We simulate word-wrapped, multi-run text by tracking a cursor.
        # Strategy: render each run's text sequentially, wrapping at bbox.width.
        # fitz.insert_text takes a single point (bottom-left of the first line).
        # We compute line breaks ourselves.

        line_height_multiplier = 1.2
        x0    = bbox.x
        y0    = bbox.y
        max_x = bbox.x + bbox.width
        max_y = bbox.y + bbox.height

        # Current cursor: start at first baseline (y0 + first run's font_size)
        cursor_x = x0
        first_run_size = node.runs[0].font_size if node.runs else node.font_size
        cursor_y = y0 + first_run_size  # fitz y = baseline

        for run in node.runs:
            fontname = _fitz_font(run.font_family, run.bold, run.italic)
            fs       = run.font_size
            rgb      = self._hex_to_rgb(run.color)
            lh       = fs * line_height_multiplier

            # Split on explicit newlines first
            segments = run.text.split('\n')
            for seg_idx, segment in enumerate(segments):
                if seg_idx > 0:
                    # Explicit newline
                    cursor_x  = x0
                    cursor_y += lh
                    if cursor_y > max_y:
                        return

                # Word-wrap within the segment
                words = segment.split(' ')
                for w_idx, word in enumerate(words):
                    piece = ('' if w_idx == 0 and cursor_x == x0 else ' ') + word
                    # Approximate char width: 0.6 × font_size per char (Helvetica heuristic)
                    piece_w = len(piece) * fs * 0.6

                    if cursor_x + piece_w > max_x and cursor_x > x0:
                        cursor_x  = x0
                        cursor_y += lh
                        if cursor_y > max_y:
                            return
                        piece = word  # drop the leading space on wrap

                    if cursor_x + len(piece) * fs * 0.6 > max_x + fs:
                        # Word itself is too long — just clip it
                        pass

                    out_page.insert_text(
                        fitz.Point(cursor_x, cursor_y),
                        piece,
                        fontsize=fs,
                        fontname=fontname,
                        color=rgb,
                        clip=clip,
                    )
                    cursor_x += len(piece) * fs * 0.6

    # ── Public export API ──────────────────────────────────────────────────────

    def export_document(self, output_path: str) -> str:
        src, out = self._build_output_doc()
        out.save(output_path)
        out.close()
        src.close()
        return output_path

    def export_to_bytes(self) -> bytes:
        src, out = self._build_output_doc()
        pdf_bytes = out.tobytes()
        out.close()
        src.close()
        return pdf_bytes

    def _build_output_doc(self):
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

            if page_node.crop_box:
                cb        = page_node.crop_box
                crop_rect = fitz.Rect(cb.x, cb.y, cb.x + cb.width, cb.y + cb.height)
                out_page.set_cropbox(crop_rect)

            self._apply_annotations(out_page, page_node)

        return src, out

    def _hex_to_rgb(self, hex_color: str) -> tuple:
        hex_color = hex_color.lstrip('#')
        if len(hex_color) != 6:
            return (0, 0, 0)
        return tuple(int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4))