"""
DrawTool — freehand and shape drawing directly onto PDF pages.

Modes
-----
pen     — freehand ink stroke (Ink annotation)
line    — straight line (Line annotation)
arrow   — line with arrowhead (Line annotation, open-arrow end)
ellipse — drag bounding box to draw ellipse (Circle annotation)

All shapes are written as native PDF annotations so they remain selectable
and editable in other viewers.  A live rubber-band preview is drawn on the
tk.Canvas while dragging; it is removed when the mouse is released and the
annotation is committed to the PDF.

Undo is handled by DrawAnnotationCommand which stores the annotation xref
and removes it on undo.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.gui.app_context import AppContext


# ── Ramer-Douglas-Peucker simplification ─────────────────────────────────────

def _rdp(points: list[tuple], epsilon: float) -> list[tuple]:
    """Reduce a polyline to fewer points while preserving shape."""
    if len(points) < 3:
        return points
    # Find the point farthest from the line start→end
    p1, p2 = points[0], points[-1]
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = math.hypot(dx, dy)
    max_dist, max_idx = 0.0, 0
    for i, p in enumerate(points[1:-1], 1):
        if length == 0:
            d = math.hypot(p[0] - p1[0], p[1] - p1[1])
        else:
            d = abs(dy * p[0] - dx * p[1] + p2[0] * p1[1] - p2[1] * p1[0]) / length
        if d > max_dist:
            max_dist, max_idx = d, i
    if max_dist > epsilon:
        left  = _rdp(points[:max_idx + 1], epsilon)
        right = _rdp(points[max_idx:],     epsilon)
        return left[:-1] + right
    return [p1, p2]


# ── DrawTool ──────────────────────────────────────────────────────────────────

class DrawTool:
    """
    Tool that lets the user draw freehand strokes and shapes onto the PDF.

    Parameters
    ----------
    ctx : AppContext
    get_mode : callable → str         "pen" | "line" | "arrow" | "ellipse"
    get_stroke_rgb : callable → tuple  (r, g, b) 0-255
    get_fill_rgb : callable → tuple | None
    get_width : callable → float
    get_opacity : callable → float     0.0–1.0
    on_committed : callable(page_idx, xref)
        Called after an annotation is successfully written to the PDF so the
        caller can push an undo command and refresh rendering.
    """

    def __init__(
        self,
        ctx: "AppContext",
        get_mode,
        get_stroke_rgb,
        get_fill_rgb,
        get_width,
        get_opacity,
        on_committed,
    ):
        self._ctx          = ctx
        self._get_mode     = get_mode
        self._get_stroke   = get_stroke_rgb
        self._get_fill     = get_fill_rgb
        self._get_width    = get_width
        self._get_opacity  = get_opacity
        self._on_committed = on_committed

        # Drag state
        self._drawing      = False
        self._start_cx: float = 0.0
        self._start_cy: float = 0.0
        self._pen_points: list[tuple[float, float]] = []
        # Offsets captured at drag start (avoids page-switching mid-drag)
        self._ox: float = 0.0
        self._oy: float = 0.0
        self._page_idx: int = 0
        self._scale: float  = 1.0
        # Shift-key state for snapping
        self._shift = False

    # ── Tool interface ────────────────────────────────────────────────────────

    def activate(self):
        canvas = self._ctx.canvas
        canvas.bind("<Shift_L>",   self._on_shift_down, add="+")
        canvas.bind("<Shift_R>",   self._on_shift_down, add="+")
        canvas.bind("<KeyRelease-Shift_L>", self._on_shift_up, add="+")
        canvas.bind("<KeyRelease-Shift_R>", self._on_shift_up, add="+")

    def deactivate(self):
        self._drawing = False
        self._ctx.canvas.delete("draw_preview")
        canvas = self._ctx.canvas
        canvas.unbind("<Shift_L>")
        canvas.unbind("<Shift_R>")
        canvas.unbind("<KeyRelease-Shift_L>")
        canvas.unbind("<KeyRelease-Shift_R>")

    def on_click(self, cx: float, cy: float):
        self._drawing     = True
        self._start_cx    = cx
        self._start_cy    = cy
        self._pen_points  = [(cx, cy)]
        # Snapshot offsets so a mid-drag page change doesn't corrupt coords
        self._ox          = self._ctx.page_offset_x
        self._oy          = self._ctx.page_offset_y
        self._page_idx    = self._ctx.current_page
        self._scale       = self._ctx.scale

    def on_drag(self, cx: float, cy: float):
        if not self._drawing:
            return
        mode = self._get_mode()
        if mode == "pen":
            self._pen_points.append((cx, cy))
        self._redraw_preview(cx, cy)

    def on_release(self, cx: float, cy: float):
        if not self._drawing:
            return
        self._drawing = False
        self._ctx.canvas.delete("draw_preview")

        mode = self._get_mode()
        if mode == "pen":
            self._pen_points.append((cx, cy))
            self._commit_pen()
        else:
            self._commit_shape(cx, cy, mode)

    # ── preview drawing ───────────────────────────────────────────────────────

    def _stroke_hex(self) -> str:
        r, g, b = self._get_stroke()
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    def _redraw_preview(self, cx: float, cy: float):
        canvas = self._ctx.canvas
        canvas.delete("draw_preview")
        mode  = self._get_mode()
        color = self._stroke_hex()
        w     = max(1, self._get_width())
        sx, sy = self._start_cx, self._start_cy
        ecx, ecy = self._snapped(sx, sy, cx, cy) if self._shift and mode != "pen" else (cx, cy)

        if mode == "pen":
            pts = self._pen_points
            if len(pts) >= 2:
                flat = [coord for p in pts for coord in p]
                canvas.create_line(
                    *flat, fill=color, width=w,
                    smooth=True, splinesteps=12, capstyle=tk.ROUND,
                    joinstyle=tk.ROUND, tags="draw_preview",
                )
        elif mode in ("line", "arrow"):
            canvas.create_line(
                sx, sy, ecx, ecy,
                fill=color, width=w, capstyle=tk.ROUND,
                arrow=tk.LAST if mode == "arrow" else tk.NONE,
                arrowshape=(12, 15, 5),
                tags="draw_preview",
            )
        elif mode == "ellipse":
            fill_hex = self._fill_hex_or_empty()
            canvas.create_oval(
                min(sx, ecx), min(sy, ecy),
                max(sx, ecx), max(sy, ecy),
                outline=color, fill=fill_hex, width=w,
                tags="draw_preview",
            )

    def _fill_hex_or_empty(self) -> str:
        fill = self._get_fill()
        if fill is None:
            return ""
        r, g, b = fill
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    @staticmethod
    def _snapped(sx, sy, cx, cy):
        """Snap end point to the nearest 45-degree angle from start."""
        dx, dy = cx - sx, cy - sy
        angle  = math.atan2(dy, dx)
        snap   = round(angle / (math.pi / 4)) * (math.pi / 4)
        dist   = math.hypot(dx, dy)
        return sx + dist * math.cos(snap), sy + dist * math.sin(snap)

    # ── PDF commit ────────────────────────────────────────────────────────────

    def _to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        """Convert canvas coords to PDF coords using the offsets captured at drag start."""
        return (
            (cx - self._ox) / self._scale,
            (cy - self._oy) / self._scale,
        )

    def _annot_colors(self):
        """Return (stroke_01, fill_01|None) tuples in 0-1 float range for fitz."""
        sr, sg, sb = self._get_stroke()
        stroke = (sr / 255, sg / 255, sb / 255)
        fill_rgb = self._get_fill()
        fill = tuple(c / 255 for c in fill_rgb) if fill_rgb else None
        return stroke, fill

    def _commit_pen(self):
        pts = self._pen_points
        if len(pts) < 2:
            return

        # Simplify with RDP before writing (reduces PDF size, smoother curve)
        simplified = _rdp(pts, epsilon=2.0)
        if len(simplified) < 2:
            simplified = [pts[0], pts[-1]]

        pdf_pts = [self._to_pdf(x, y) for x, y in simplified]

        doc = self._ctx.canvas.master   # not clean but we need PDFDocument
        # Reach the PDFDocument via AppContext
        try:
            self._write_ink(pdf_pts)
        except Exception as ex:
            import tkinter.messagebox as mb
            mb.showerror("Draw Error", str(ex))

    def _commit_shape(self, cx: float, cy: float, mode: str):
        sx, sy = self._start_cx, self._start_cy
        if self._shift:
            cx, cy = self._snapped(sx, sy, cx, cy)
        try:
            if mode in ("line", "arrow"):
                self._write_line(sx, sy, cx, cy, arrow=(mode == "arrow"))
            elif mode == "ellipse":
                self._write_ellipse(sx, sy, cx, cy)
        except Exception as ex:
            import tkinter.messagebox as mb
            mb.showerror("Draw Error", str(ex))

    def _write_ink(self, pdf_pts: list[tuple]):
        import fitz
        page_idx = self._page_idx
        doc      = self._ctx._editor.doc
        if not doc:
            return
        fitz_page = doc.get_page(page_idx)._page
        # Pass plain (x, y) tuples — fitz.Point not accepted in all versions
        ink_list  = [[(float(x), float(y)) for x, y in pdf_pts]]
        annot     = fitz_page.add_ink_annot(ink_list)
        stroke, _ = self._annot_colors()
        annot.set_colors(stroke=stroke)
        annot.set_border(width=self._get_width())
        annot.set_opacity(self._get_opacity())
        annot.update()
        xref = annot.xref
        self._on_committed(page_idx, xref)

    def _write_line(self, sx, sy, ex, ey, arrow: bool):
        import fitz
        page_idx  = self._page_idx
        doc       = self._ctx._editor.doc
        if not doc:
            return
        # Plain tuples — accepted by all fitz versions
        p1        = self._to_pdf(sx, sy)
        p2        = self._to_pdf(ex, ey)
        fitz_page = doc.get_page(page_idx)._page
        annot     = fitz_page.add_line_annot(p1, p2)
        stroke, _ = self._annot_colors()
        annot.set_colors(stroke=stroke)
        annot.set_border(width=self._get_width())
        annot.set_opacity(self._get_opacity())
        if arrow:
            annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
        annot.update()
        xref = annot.xref
        self._on_committed(page_idx, xref)

    def _write_ellipse(self, sx, sy, ex, ey):
        import fitz
        page_idx  = self._page_idx
        doc       = self._ctx._editor.doc
        if not doc:
            return
        px0, py0  = self._to_pdf(min(sx, ex), min(sy, ey))
        px1, py1  = self._to_pdf(max(sx, ex), max(sy, ey))
        if abs(px1 - px0) < 2 or abs(py1 - py0) < 2:
            return   # too small, skip
        # Plain 4-tuple rect — accepted by all fitz versions
        rect      = (px0, py0, px1, py1)
        fitz_page = doc.get_page(page_idx)._page
        annot     = fitz_page.add_circle_annot(rect)
        stroke, fill = self._annot_colors()
        colors = {"stroke": stroke}
        if fill:
            colors["fill"] = fill
        annot.set_colors(**colors)
        annot.set_border(width=self._get_width())
        annot.set_opacity(self._get_opacity())
        annot.update()
        xref = annot.xref
        self._on_committed(page_idx, xref)

    # ── shift key tracking ────────────────────────────────────────────────────

    def _on_shift_down(self, event):
        self._shift = True

    def _on_shift_up(self, event):
        self._shift = False