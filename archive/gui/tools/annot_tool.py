"""
AnnotationTool — rubber-band drag to place highlight or rectangle annotations.

Handles both the "highlight" and "rect_annot" tool modes; the mode is
passed at construction so a single class covers both use-cases.
"""

import tkinter as tk
from tkinter import messagebox

from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE
from src.commands.annotate import AddHighlightCommand, AddRectAnnotationCommand


def _rgb255_to_hex(rgb: tuple) -> str:
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"


def _rgb255_to_float(rgb: tuple) -> tuple:
    return tuple(v / 255.0 for v in rgb)


class AnnotationTool(BaseTool):
    """
    Rubber-band drag → commit as a highlight or rect annotation.

    Parameters
    ----------
    ctx : AppContext
    annotation_service : AnnotationService
    mode : str
        Either ``"highlight"`` or ``"rect_annot"``.
    get_stroke_rgb : callable → tuple
        Returns the current stroke colour as an (R, G, B) 0-255 tuple.
    get_fill_rgb : callable → tuple | None
        Returns the current fill colour, or None for transparent.
    get_width : callable → float
        Returns the current stroke width.
    """

    # Minimum drag size in canvas pixels before we commit
    MIN_DRAG_PX = 6

    def __init__(
        self,
        ctx,
        annotation_service,
        mode: str,
        get_stroke_rgb,
        get_fill_rgb,
        get_width,
    ):
        super().__init__(ctx)
        self._service       = annotation_service
        self._mode          = mode
        self._get_stroke    = get_stroke_rgb
        self._get_fill      = get_fill_rgb
        self._get_width     = get_width

        self._drag_start: tuple | None = None
        self._rubber_band: int | None  = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self):
        self.ctx.canvas.config(cursor="crosshair")

    def deactivate(self):
        self._cancel()

    # ── events ────────────────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float):
        self._drag_start  = (canvas_x, canvas_y)
        self._rubber_band = None

    def on_drag(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start
        outline = (
            "#FFD700"
            if self._mode == "highlight"
            else _rgb255_to_hex(self._get_stroke())
        )
        if self._rubber_band is None:
            self._rubber_band = self.ctx.canvas.create_rectangle(
                x0, y0, canvas_x, canvas_y,
                outline=outline, width=2, dash=(4, 3),
            )
        else:
            self.ctx.canvas.coords(self._rubber_band, x0, y0, canvas_x, canvas_y)

    def on_release(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None:
            return

        x0, y0 = self._drag_start
        self._cancel_rubber_band()
        self._drag_start = None

        if abs(canvas_x - x0) < self.MIN_DRAG_PX or abs(canvas_y - y0) < self.MIN_DRAG_PX:
            return

        px0, py0 = self._canvas_to_pdf(min(x0, canvas_x), min(y0, canvas_y))
        px1, py1 = self._canvas_to_pdf(max(x0, canvas_x), max(y0, canvas_y))
        rect = (px0, py0, px1, py1)

        if self._mode == "highlight":
            cmd = AddHighlightCommand(
                self._service, self.ctx.doc,
                self.ctx.current_page, rect,
            )
            label = "Highlight"
        else:
            stroke = _rgb255_to_float(self._get_stroke())
            raw_fill = self._get_fill()
            fill   = _rgb255_to_float(raw_fill) if raw_fill is not None else None
            cmd = AddRectAnnotationCommand(
                self._service, self.ctx.doc,
                self.ctx.current_page, rect,
                color=stroke, fill=fill, width=self._get_width(),
            )
            label = "Rectangle"

        try:
            cmd.execute()
            self.ctx.push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Annotation Error", str(ex))
            return

        self.ctx.flash_status(f"✓ {label} annotation added")
        self.ctx.render()

    # ── internals ─────────────────────────────────────────────────────────────

    def _cancel_rubber_band(self):
        if self._rubber_band is not None:
            self.ctx.canvas.delete(self._rubber_band)
            self._rubber_band = None

    def _cancel(self):
        self._cancel_rubber_band()
        self._drag_start = None