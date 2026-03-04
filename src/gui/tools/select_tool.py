"""
SelectTextTool — click or rubber-band drag to select and copy PDF text blocks.

Text blocks are loaded from PyMuPDF's get_text("blocks") call when the tool
activates (or the page changes).  Invisible hit-target rectangles are drawn
over each block on the canvas; a visible highlight overlay is shown for
selected blocks.
"""

import tkinter as tk

from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE


class SelectTextTool(BaseTool):
    """
    Click a text block to select/deselect it.
    Drag a rubber-band to select multiple overlapping blocks.
    Ctrl+C (or automatic after release) copies selected text to the clipboard.
    """

    def __init__(self, ctx, root: tk.Tk):
        super().__init__(ctx)
        self._root = root

        self._blocks: list       = []   # (x0, y0, x1, y1, text)
        self._hit_ids: list[int] = []   # canvas item IDs for hit targets
        self._hl_ids: list[int]  = []   # canvas item IDs for highlight overlays
        self._selected: set[int] = set()

        self._drag_start: tuple | None = None
        self._rubber_band: int | None  = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self):
        self.ctx.canvas.config(cursor="ibeam")
        self._load_blocks()

    def deactivate(self):
        self.clear()

    # ── public helpers (called by main window on page change) ─────────────────

    def reload(self):
        """Re-load text blocks after a page change or re-render."""
        self.clear()
        self._load_blocks()

    def copy(self):
        """Copy all selected block text to the system clipboard."""
        if not self._selected or not self._blocks:
            return
        ordered = sorted(
            self._selected,
            key=lambda i: (self._blocks[i][1], self._blocks[i][0]),
        )
        combined = "\n\n".join(self._blocks[i][4] for i in ordered)
        if not combined:
            return
        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(combined)
            self._root.update()
        except Exception:
            pass
        count = len(self._selected)
        label = "block" if count == 1 else "blocks"
        self.ctx.flash_status(f"✓ Copied {count} text {label} to clipboard")

    def clear(self):
        """Remove all canvas overlays and reset internal state."""
        self.ctx.canvas.delete("textsel")
        self._blocks    = []
        self._hit_ids   = []
        self._hl_ids    = []
        self._selected  = set()
        if self._rubber_band is not None:
            self.ctx.canvas.delete(self._rubber_band)
            self._rubber_band = None
        self._drag_start = None

    # ── events ────────────────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float):
        self._clear_selection()
        self._drag_start  = (canvas_x, canvas_y)
        self._rubber_band = None

    def on_drag(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start
        if self._rubber_band is None:
            self._rubber_band = self.ctx.canvas.create_rectangle(
                x0, y0, canvas_x, canvas_y,
                outline=PALETTE["accent_light"],
                fill=PALETTE["accent_dim"],
                width=1, stipple="gray25",
            )
        else:
            self.ctx.canvas.coords(self._rubber_band, x0, y0, canvas_x, canvas_y)
        self._update_from_drag(
            min(x0, canvas_x), min(y0, canvas_y),
            max(x0, canvas_x), max(y0, canvas_y),
        )

    def on_release(self, canvas_x: float, canvas_y: float):
        if self._rubber_band is not None:
            self.ctx.canvas.delete(self._rubber_band)
            self._rubber_band = None

        if self._drag_start is None:
            return
        x0, y0          = self._drag_start
        self._drag_start = None

        is_click = abs(canvas_x - x0) < 5 and abs(canvas_y - y0) < 5
        if is_click:
            pdf_x, pdf_y = self._canvas_to_pdf(canvas_x, canvas_y)
            for i, (bx0, by0, bx1, by1, _txt) in enumerate(self._blocks):
                if bx0 <= pdf_x <= bx1 and by0 <= pdf_y <= by1:
                    self._toggle_block(i)
                    break

        if self._selected:
            self.copy()

    def on_motion(self, canvas_x: float, canvas_y: float):
        """Show faint hover tint when not in a drag."""
        if self._drag_start is not None:
            return
        pdf_x, pdf_y = self._canvas_to_pdf(canvas_x, canvas_y)
        for i, (x0, y0, x1, y1, _txt) in enumerate(self._blocks):
            if i in self._selected:
                continue
            inside = x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1
            if i < len(self._hl_ids):
                hl = self._hl_ids[i]
                if inside:
                    self.ctx.canvas.itemconfig(
                        hl, state="normal",
                        fill=PALETTE["fg_dim"], stipple="gray50",
                    )
                else:
                    self.ctx.canvas.itemconfig(hl, state="hidden")

    # ── internals ─────────────────────────────────────────────────────────────

    def _load_blocks(self):
        if not self.ctx.doc:
            return
        page = self.ctx.doc.get_page(self.ctx.current_page)
        raw  = page.get_text_blocks()
        self._blocks = [
            (x0, y0, x1, y1, txt.strip())
            for x0, y0, x1, y1, txt, _bno, btype in raw
            if btype == 0 and txt.strip()
        ]
        self._hit_ids = []
        self._hl_ids  = []
        self._selected = set()

        ox = self.ctx.page_offset_x
        oy = self.ctx.page_offset_y
        s  = self.ctx.scale

        for i, (x0, y0, x1, y1, _txt) in enumerate(self._blocks):
            cx0, cy0 = ox + x0 * s, oy + y0 * s
            cx1, cy1 = ox + x1 * s, oy + y1 * s

            self.ctx.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=PALETTE["fg_dim"], width=1, dash=(3, 6),
                fill="", tags=("textsel", f"textsel_outline_{i}"),
            )
            hl_id = self.ctx.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                fill=PALETTE["accent"], outline=PALETTE["accent_light"],
                width=1, stipple="gray25",
                tags=("textsel", f"textsel_hl_{i}"),
            )
            self.ctx.canvas.itemconfig(hl_id, state="hidden")

            hit_id = self.ctx.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                fill="", outline="",
                tags=("textsel", f"textsel_hit_{i}"),
            )
            self._hit_ids.append(hit_id)
            self._hl_ids.append(hl_id)

    def _clear_selection(self):
        for i in list(self._selected):
            if i < len(self._hl_ids):
                self.ctx.canvas.itemconfig(self._hl_ids[i], state="hidden")
        self._selected = set()

    def _toggle_block(self, idx: int):
        if idx in self._selected:
            self._selected.discard(idx)
            if idx < len(self._hl_ids):
                self.ctx.canvas.itemconfig(self._hl_ids[idx], state="hidden")
        else:
            self._selected.add(idx)
            if idx < len(self._hl_ids):
                self.ctx.canvas.itemconfig(
                    self._hl_ids[idx], state="normal",
                    fill=PALETTE["accent"], stipple="gray25",
                )

    def _update_from_drag(self, cx0: float, cy0: float, cx1: float, cy1: float):
        ox = self.ctx.page_offset_x
        oy = self.ctx.page_offset_y
        s  = self.ctx.scale
        for i, (bx0, by0, bx1, by1, _txt) in enumerate(self._blocks):
            bcx0 = ox + bx0 * s
            bcy0 = oy + by0 * s
            bcx1 = ox + bx1 * s
            bcy1 = oy + by1 * s
            overlaps = not (bcx1 < cx0 or bcx0 > cx1 or bcy1 < cy0 or bcy0 > cy1)
            hl = self._hl_ids[i] if i < len(self._hl_ids) else None
            if overlaps:
                self._selected.add(i)
                if hl:
                    self.ctx.canvas.itemconfig(
                        hl, state="normal",
                        fill=PALETTE["accent"], stipple="gray25",
                    )
            else:
                self._selected.discard(i)
                if hl:
                    self.ctx.canvas.itemconfig(hl, state="hidden")