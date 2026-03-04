"""
SelectTextTool — click-drag text selection with character-level precision.

Architecture
------------
This tool owns ONLY selection state — it never draws canvas items.
The highlight is rendered by compositing a semi-transparent blue rectangle
directly into the PIL page image before it becomes a tk.PhotoImage.
This gives a perfectly smooth, anti-aliased highlight identical to a browser
or native PDF viewer.

The rendering pipeline calls ``get_highlight_rects_for_page(page_idx)`` to
retrieve the current selection as a list of PDF-space (x0,y0,x1,y1) rects
(one per line), then blends them onto the image with PIL before display.

Whenever the selection changes the tool calls ``ctx.render()`` so the window
re-runs its normal render path — the compositing happens automatically.

Interaction model
-----------------
• Mouse-down  : anchor the selection start at the nearest character.
• Mouse-drag  : extend selection live; re-renders on every motion event.
• Mouse-up    : finalise; auto-copies to clipboard if text was selected.
• Click empty : clears selection.
• Ctrl+C      : explicit copy.
• on_motion() : ibeam cursor over text, arrow elsewhere.
"""

from __future__ import annotations

import tkinter as tk
from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE


class SelectTextTool(BaseTool):

    def __init__(self, ctx, root: tk.Tk) -> None:
        super().__init__(ctx)
        self._root = root

        # Flat list of character records for the current page.
        # Each entry: {"bbox": (x0,y0,x1,y1), "c": str,
        #              "line_idx": int, "block_idx": int}
        self._chars: list[dict] = []

        # Anchor (mouse-down) and head (current drag end) indices into _chars
        self._anchor_idx: int | None = None
        self._head_idx:   int | None = None

        self._dragging = False

        # Track the last rendered selection so we only re-render on change
        self._last_rendered_range: tuple[int, int] | None = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self) -> None:
        self.ctx.canvas.config(cursor="ibeam")
        self._load_chars()

    def deactivate(self) -> None:
        # Clear selection and force a clean render to remove the highlight
        had_selection = self._anchor_idx is not None
        self._chars      = []
        self._anchor_idx = None
        self._head_idx   = None
        self._dragging   = False
        self._last_rendered_range = None
        if had_selection:
            self.ctx.render()

    def reload(self) -> None:
        """Re-load after a page change or re-render (called by main_window)."""
        self._anchor_idx  = None
        self._head_idx    = None
        self._dragging    = False
        self._last_rendered_range = None
        self._load_chars()

    # ── public API for the render pipeline ────────────────────────────────────

    def get_highlight_rects_for_page(self, page_idx: int) -> list[tuple]:
        """
        Return a list of (x0, y0, x1, y1) rects in PDF user-space points,
        one per selected line, for the given page.

        Returns [] when there is no selection or the selection is on a
        different page.  Called by main_window during render.
        """
        if page_idx != self.ctx.current_page:
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
        pdf_x, pdf_y = self._canvas_to_pdf(canvas_x, canvas_y)
        over_text = any(
            ch["bbox"][0] <= pdf_x <= ch["bbox"][2] and
            ch["bbox"][1] <= pdf_y <= ch["bbox"][3]
            for ch in self._chars
        )
        self.ctx.canvas.config(cursor="ibeam" if over_text else "arrow")

    # ── internals ─────────────────────────────────────────────────────────────

    def _trigger_render_if_changed(self) -> None:
        """Only call ctx.render() when the selection range actually changes."""
        rng = self._selection_range()
        if rng != self._last_rendered_range:
            self._last_rendered_range = rng
            self.ctx.render()

    def _load_chars(self) -> None:
        self._chars = []
        if not self.ctx.doc:
            return
        page    = self.ctx.doc.get_page(self.ctx.current_page)
        rawdict = page.get_text_rawdict()
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
        ox = self.ctx.page_offset_x
        oy = self.ctx.page_offset_y
        s  = self.ctx.scale
        return (cx - ox) / s, (cy - oy) / s