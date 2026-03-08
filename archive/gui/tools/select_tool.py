# src/gui/tools/select_tool.py

from __future__ import annotations

import tkinter as tk
from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE, PAD_XL


class SelectTextTool(BaseTool):

    def __init__(self, ctx, root: tk.Tk) -> None:
        super().__init__(ctx)
        self._root = root

        # Dictionary caching character data for any page we have touched.
        # Format: { page_idx: [ char_dict, ... ] }
        self._pages_chars: dict[int, list[dict]] = {}

        # Anchor and head are now tuples of (page_idx, local_char_idx).
        # This allows us to smoothly track selections across page boundaries.
        self._anchor: tuple[int, int] | None = None
        self._head:   tuple[int, int] | None = None

        self._dragging = False
        self._last_rendered_range: tuple | None = None

        # Track exactly which pages have a highlight drawn on them so we can
        # cleanly wipe them from the continuous scroll cache when clearing.
        self._highlighted_pages: set[int] = set()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self) -> None:
        self.ctx.canvas.config(cursor="ibeam")
        self._pages_chars = {}

    def deactivate(self) -> None:
        had_selection = self._anchor is not None
        self._pages_chars = {}
        self._anchor = None
        self._head   = None
        self._dragging = False
        self._last_rendered_range = None
        
        pages_to_refresh = set(self._highlighted_pages)
        
        if had_selection and hasattr(self.ctx, "invalidate_cache"):
            for p in pages_to_refresh:
                self.ctx.invalidate_cache(p)
                
        self._highlighted_pages.clear()
        
        # Use targeted refresh to avoid flashing and blanking when switching tools
        if had_selection:
            editor = self.ctx._editor
            if getattr(editor, "_continuous_mode", False) and hasattr(editor, "_render_cont_page_refresh"):
                for p in pages_to_refresh:
                    editor._render_cont_page_refresh(p)
            else:
                self.ctx.render()

    def reload(self) -> None:
        had_selection = self._anchor is not None
        self._anchor = None
        self._head   = None
        self._dragging = False
        self._last_rendered_range = None
        
        if had_selection and hasattr(self.ctx, "invalidate_cache"):
            for p in self._highlighted_pages:
                self.ctx.invalidate_cache(p)
        self._highlighted_pages.clear()

    # ── public API for the render pipeline ────────────────────────────────────

    def get_highlight_rects_for_page(self, page_idx: int) -> list[tuple]:
        """Return highlight rects specifically for the requested page."""
        if not self._anchor or not self._head:
            return []
            
        start_p, start_i = min(self._anchor, self._head)
        end_p, end_i     = max(self._anchor, self._head)
        
        # If this page is outside our selection bounds, it has no highlights
        if not (start_p <= page_idx <= end_p):
            return []
            
        if page_idx not in self._pages_chars:
            return []
            
        page_chars = self._pages_chars[page_idx]
        
        # Determine local start and end indices for this specific page slice
        s_idx = start_i if page_idx == start_p else 0
        e_idx = end_i if page_idx == end_p else len(page_chars) - 1
        
        selected = page_chars[s_idx : e_idx + 1]
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
        new_anchor = self._nearest_char(canvas_x, canvas_y)
        
        # If we clicked on empty space (not near any text), clear the selection
        if new_anchor is None:
            if self._anchor is not None:
                self._anchor = None
                self._head = None
                # Let the trigger safely invalidate and redraw the old pages
                self._trigger_render_if_changed()
            return

        self._dragging = True
        self._anchor = new_anchor
        self._head   = new_anchor
        self._trigger_render_if_changed()

    def on_drag(self, canvas_x: float, canvas_y: float) -> None:
        if not self._dragging or self._anchor is None:
            return
            
        # Auto-scroll logic when dragging near the window edges
        c = self.ctx.canvas
        ch = c.winfo_height()
        view_y = canvas_y - c.canvasy(0)
        
        scroll_margin = 35
        if view_y < scroll_margin:
            c.yview_scroll(-1, "units")
            canvas_y = c.canvasy(view_y)
        elif view_y > ch - scroll_margin:
            c.yview_scroll(1, "units")
            canvas_y = c.canvasy(view_y)

        # Update selection head across whatever page it is now on
        new_head = self._nearest_char(canvas_x, canvas_y)
        if new_head is not None and new_head != self._head:
            self._head = new_head
            self._trigger_render_if_changed()

    def on_release(self, canvas_x: float, canvas_y: float) -> None:
        self._dragging = False
        if self._anchor is None:
            return
            
        new_head = self._nearest_char(canvas_x, canvas_y)
        if new_head is not None:
            self._head = new_head
            self._trigger_render_if_changed()
            
        text = self._selection_text()
        if text and text.strip():
            self.copy()

    def on_motion(self, canvas_x: float, canvas_y: float) -> None:
        if self._dragging:
            return
            
        p, ox, oy = self._resolve_page_and_offsets(canvas_y)
        if p not in self._pages_chars:
            self._load_chars_for_page(p)
            
        chars = self._pages_chars.get(p, [])
        s = self.ctx.scale
        pdf_x = (canvas_x - ox) / s
        pdf_y = (canvas_y - oy) / s
        
        over_text = any(
            ch["bbox"][0] <= pdf_x <= ch["bbox"][2] and
            ch["bbox"][1] <= pdf_y <= ch["bbox"][3]
            for ch in chars
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
        rng = (self._anchor, self._head)
        if rng != self._last_rendered_range:
            self._last_rendered_range = rng
            
            # Figure out which pages are currently selected
            new_pages = set()
            if self._anchor and self._head:
                start_p = min(self._anchor[0], self._head[0])
                end_p   = max(self._anchor[0], self._head[0])
                new_pages = set(range(start_p, end_p + 1))
                
            # We must invalidate both the old pages (to remove old highlights)
            # and the new pages (to draw new highlights).
            pages_to_invalidate = self._highlighted_pages.union(new_pages)
            
            if hasattr(self.ctx, "invalidate_cache"):
                for p in pages_to_invalidate:
                    self.ctx.invalidate_cache(p)
                    
            self._highlighted_pages = new_pages
            
            # Targeted Render: prevent full-canvas teardown and flashing
            editor = self.ctx._editor
            if getattr(editor, "_continuous_mode", False):
                # Only redraw the specific pages affected by the selection change
                if hasattr(editor, "_render_cont_page_refresh"):
                    for p in pages_to_invalidate:
                        editor._render_cont_page_refresh(p)
            else:
                # Single-page mode simply re-renders the current screen
                self.ctx.render()

    def _load_chars_for_page(self, page_idx: int) -> None:
        if not self.ctx.doc:
            return
        try:
            page = self.ctx.doc.get_page(page_idx)
            rawdict = page.get_text_rawdict()
        except Exception:
            return
            
        if not rawdict:
            self._pages_chars[page_idx] = []
            return

        chars = []
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
                        chars.append({
                            "bbox":      tuple(bbox),
                            "c":         c,
                            "line_idx":  line_counter,
                            "block_idx": block_idx,
                        })
                line_counter += 1

        # Reading order: top-to-bottom, left-to-right
        chars.sort(key=lambda ch: (round(ch["bbox"][1]), ch["bbox"][0]))
        self._pages_chars[page_idx] = chars

    def _nearest_char(self, canvas_x: float, canvas_y: float) -> tuple[int, int] | None:
        p, ox, oy = self._resolve_page_and_offsets(canvas_y)
        
        if p not in self._pages_chars:
            self._load_chars_for_page(p)
            
        chars = self._pages_chars.get(p, [])
        if not chars:
            return None
            
        s = self.ctx.scale
        pdf_x = (canvas_x - ox) / s
        pdf_y = (canvas_y - oy) / s

        # Prefer exact bbox hit
        exact: list[tuple[float, int]] = []
        for i, ch in enumerate(chars):
            x0, y0, x1, y1 = ch["bbox"]
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                exact.append(((pdf_x - cx) ** 2 + (pdf_y - cy) ** 2, i))
                
        if exact:
            return (p, min(exact)[1])

        # Fall back to nearest centre, but with a maximum distance threshold
        best_d, best_i = float("inf"), -1
        MAX_DIST_SQ = 400  # About 20 PDF points squared
        
        for i, ch in enumerate(chars):
            x0, y0, x1, y1 = ch["bbox"]
            d = (pdf_x - (x0+x1)/2) ** 2 + (pdf_y - (y0+y1)/2) ** 2
            if d < best_d:
                best_d, best_i = d, i
                
        # Return tuple (page_index, local_char_index) if within threshold
        if best_d <= MAX_DIST_SQ and best_i >= 0:
            return (p, best_i)
            
        return None

    def _selection_text(self) -> str:
        if not self._anchor or not self._head:
            return ""
            
        start_p, start_i = min(self._anchor, self._head)
        end_p, end_i     = max(self._anchor, self._head)
        
        result     = []
        prev_line  = None
        prev_block = None
        
        for p in range(start_p, end_p + 1):
            if p not in self._pages_chars:
                continue
                
            chars = self._pages_chars[p]
            s = start_i if p == start_p else 0
            e = end_i if p == end_p else len(chars) - 1
            
            selected = chars[s : e + 1]
            for ch in selected:
                if prev_block is not None and ch["block_idx"] != prev_block:
                    result.append("\n\n")
                elif prev_line is not None and ch["line_idx"] != prev_line:
                    result.append("\n")
                    
                prev_line  = ch["line_idx"]
                prev_block = ch["block_idx"]
                result.append(ch["c"])
                
            # Add a visual separation between pages
            if p < end_p:
                result.append("\n\n")
                prev_line = None
                prev_block = None
                
        return "".join(result)