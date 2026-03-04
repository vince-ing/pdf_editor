# src/gui/tools/select_tool.py

from __future__ import annotations

import tkinter as tk
from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE, PAD_XL


class SelectTextTool(BaseTool):

    def __init__(self, ctx, root: tk.Tk) -> None:
        super().__init__(ctx)
        self._root = root

        # Flat list of character records for the locked page.
        self._chars: list[dict] = []

        # Anchor (mouse-down) and head (current drag end) indices into _chars
        self._anchor_idx: int | None = None
        self._head_idx:   int | None = None

        self._dragging = False

        # Track the last rendered selection so we only re-render on change
        self._last_rendered_range: tuple[int, int] | None = None

        # Lock state for the page currently being interacted with.
        # This prevents continuous scrolling from shifting the math underneath the tool.
        self._active_page_idx: int | None = None
        self._active_offset_x: float = 0.0
        self._active_offset_y: float = 0.0
        self._active_scale: float = 1.0

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self) -> None:
        self.ctx.canvas.config(cursor="ibeam")
        # Defer loading characters until the user actually interacts or hovers
        self._chars = []
        self._active_page_idx = None

    def deactivate(self) -> None:
        had_selection = self._anchor_idx is not None
        self._chars      = []
        self._anchor_idx = None
        self._head_idx   = None
        self._dragging   = False
        self._last_rendered_range = None
        page_to_invalidate = self._active_page_idx
        self._active_page_idx = None
        
        if had_selection:
            if hasattr(self.ctx, "invalidate_cache") and page_to_invalidate is not None:
                self.ctx.invalidate_cache(page_to_invalidate)
            self.ctx.render()

    def reload(self) -> None:
        """Re-load after a page change or re-render (called by main_window)."""
        had_selection = self._anchor_idx is not None
        self._anchor_idx  = None
        self._head_idx    = None
        self._dragging    = False
        self._last_rendered_range = None
        if had_selection and hasattr(self.ctx, "invalidate_cache") and self._active_page_idx is not None:
            self.ctx.invalidate_cache(self._active_page_idx)
        # We don't blind-load chars here anymore; we lazy load on interaction

    # ── public API for the render pipeline ────────────────────────────────────

    def get_highlight_rects_for_page(self, page_idx: int) -> list[tuple]:
        """
        Return a list of (x0, y0, x1, y1) rects in PDF user-space points.
        Checks against the tool's locked active page, not the global current page.
        """
        if self._active_page_idx is None or page_idx != self._active_page_idx:
            return []
            
        rng = self._selection_range()
        if rng is None:
            return []
        lo, hi = rng
        selected = self._chars[lo : hi + 1]
        if not selected:
            return []

        # Group by line_idx
        lines: dict[int, list[dict]] = {}
        for ch in selected:
            lines.setdefault(ch["line_idx"], []).append(ch)

        rects = []
        for line_chars in lines.values():
            x0 = min(ch["bbox"][0] for ch in line_chars)
            y0 = min(ch["bbox"][1] for ch in line_chars)
            x1 = max(ch["bbox"][2] for ch in line_chars)
            y1 = max(ch["bbox"][3] for ch in line_chars)
            rects.append((x0, y0, x1, y1))
        return rects

    # ── clipboard ─────────────────────────────────────────────────────────────

    def copy(self) -> None:
        text = self._selection_text()
        if not text:
            return
        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            self._root.update()
        except Exception:
            pass
        self.ctx.flash_status("✓ Copied selected text to clipboard")

    # ── mouse events ─────────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float) -> None:
        page_idx, ox, oy = self._resolve_page_and_offsets(canvas_y)
        
        # If we clicked a different page, reload chars for THAT specific page
        if page_idx != self._active_page_idx or not self._chars:
            self._active_page_idx = page_idx
            self._load_chars_for_page(page_idx)
            
        # Lock the offsets for the duration of this drag interaction
        self._active_offset_x = ox
        self._active_offset_y = oy
        self._active_scale = self.ctx.scale
        
        self._dragging   = True
        self._anchor_idx = self._nearest_char(canvas_x, canvas_y)
        self._head_idx   = self._anchor_idx
        self._trigger_render_if_changed()

    def on_drag(self, canvas_x: float, canvas_y: float) -> None:
        if not self._dragging or self._anchor_idx is None:
            return
        new_head = self._nearest_char(canvas_x, canvas_y)
        if new_head != self._head_idx:
            self._head_idx = new_head
            self._trigger_render_if_changed()

    def on_release(self, canvas_x: float, canvas_y: float) -> None:
        self._dragging = False
        if self._anchor_idx is None:
            return
        self._head_idx = self._nearest_char(canvas_x, canvas_y)
        self._trigger_render_if_changed()
        text = self._selection_text()
        if text and text.strip():
            self.copy()

    def on_motion(self, canvas_x: float, canvas_y: float) -> None:
        if self._dragging:
            return
            
        # Dynamically switch the loaded page context if we hover over a different page
        page_idx, ox, oy = self._resolve_page_and_offsets(canvas_y)
        if page_idx != self._active_page_idx or not self._chars:
            self._active_page_idx = page_idx
            self._load_chars_for_page(page_idx)
            
        self._active_offset_x = ox
        self._active_offset_y = oy
        self._active_scale = self.ctx.scale
        
        pdf_x, pdf_y = self._canvas_to_pdf(canvas_x, canvas_y)
        over_text = any(
            ch["bbox"][0] <= pdf_x <= ch["bbox"][2] and
            ch["bbox"][1] <= pdf_y <= ch["bbox"][3]
            for ch in self._chars
        )
        self.ctx.canvas.config(cursor="ibeam" if over_text else "arrow")

    # ── internals ─────────────────────────────────────────────────────────────

    def _resolve_page_and_offsets(self, cy: float) -> tuple[int, float, float]:
        """Ask the editor which page is under the cursor and get its exact offsets."""
        editor = self.ctx._editor
        if getattr(editor, "_continuous_mode", False) and self.ctx.doc:
            page_idx = editor._cont_page_at_y(cy)
            oy = editor._cont_page_top(page_idx)
            try:
                p = self.ctx.doc.get_page(page_idx)
                iw = int(p.width * self.ctx.scale)
                cw = self.ctx.canvas.winfo_width()
                ox = max(PAD_XL, (cw - iw) // 2)
            except Exception:
                ox = self.ctx.page_offset_x
            return page_idx, ox, oy
        else:
            return self.ctx.current_page, self.ctx.page_offset_x, self.ctx.page_offset_y

    def _trigger_render_if_changed(self) -> None:
        """Only call ctx.render() when the selection range actually changes."""
        rng = self._selection_range()
        if rng != self._last_rendered_range:
            self._last_rendered_range = rng
            if hasattr(self.ctx, "invalidate_cache") and self._active_page_idx is not None:
                self.ctx.invalidate_cache(self._active_page_idx)
            self.ctx.render()

    def _load_chars_for_page(self, page_idx: int) -> None:
        self._chars = []
        if not self.ctx.doc:
            return
        try:
            page = self.ctx.doc.get_page(page_idx)
            rawdict = page.get_text_rawdict()
        except Exception:
            return
            
        if not rawdict:
            return

        line_counter = 0
        for block_idx, block in enumerate(rawdict.get("blocks", [])):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    for ch in span.get("chars", []):
                        c    = ch.get("c", "")
                        bbox = ch.get("bbox")
                        if not c or bbox is None:
                            continue
                        self._chars.append({
                            "bbox":      tuple(bbox),
                            "c":         c,
                            "line_idx":  line_counter,
                            "block_idx": block_idx,
                        })
                line_counter += 1

        # Reading order: top-to-bottom, left-to-right
        self._chars.sort(key=lambda ch: (round(ch["bbox"][1]), ch["bbox"][0]))

    def _nearest_char(self, canvas_x: float, canvas_y: float) -> int | None:
        if not self._chars:
            return None
        pdf_x, pdf_y = self._canvas_to_pdf(canvas_x, canvas_y)

        # Prefer exact bbox hit
        exact: list[tuple[float, int]] = []
        for i, ch in enumerate(self._chars):
            x0, y0, x1, y1 = ch["bbox"]
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                exact.append(((pdf_x - cx) ** 2 + (pdf_y - cy) ** 2, i))
        if exact:
            return min(exact)[1]

        # Fall back to nearest centre
        best_d, best_i = float("inf"), 0
        for i, ch in enumerate(self._chars):
            x0, y0, x1, y1 = ch["bbox"]
            d = (pdf_x - (x0+x1)/2) ** 2 + (pdf_y - (y0+y1)/2) ** 2
            if d < best_d:
                best_d, best_i = d, i
        return best_i

    def _selection_range(self) -> tuple[int, int] | None:
        if self._anchor_idx is None or self._head_idx is None:
            return None
        return min(self._anchor_idx, self._head_idx), \
               max(self._anchor_idx, self._head_idx)

    def _selection_text(self) -> str:
        rng = self._selection_range()
        if not rng:
            return ""
        lo, hi = rng
        selected = self._chars[lo : hi + 1]
        if not selected:
            return ""
        result     = []
        prev_line  = selected[0]["line_idx"]
        prev_block = selected[0]["block_idx"]
        for ch in selected:
            if ch["block_idx"] != prev_block:
                result.append("\n\n")
                prev_block = ch["block_idx"]
                prev_line  = ch["line_idx"]
            elif ch["line_idx"] != prev_line:
                result.append("\n")
                prev_line = ch["line_idx"]
            result.append(ch["c"])
        return "".join(result)

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        """Convert using the specific locked coordinates of the active page."""
        ox = self._active_offset_x
        oy = self._active_offset_y
        s  = self._active_scale
        return (cx - ox) / s, (cy - oy) / s