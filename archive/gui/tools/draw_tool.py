"""
DrawTool — freehand and shape drawing directly onto PDF pages.

Modes
-----
pen     — freehand ink stroke (Ink annotation)
line    — straight line (Line annotation)
arrow   — line with arrowhead (Line annotation, open-arrow end)
ellipse — drag bounding box to draw ellipse (Circle annotation)

All PDF writing is delegated to ``AnnotationService`` so this module
contains zero fitz imports and no direct document access.  A live
rubber-band preview is drawn on the tk.Canvas while dragging; it is
removed when the mouse is released and the annotation is committed.

Undo is handled by DrawAnnotationCommand which stores the annotation
xref and removes it on undo.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.gui.app_context import AppContext
    from src.services.annotation_service import AnnotationService


# ── Ramer-Douglas-Peucker simplification ─────────────────────────────────────

def _rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    """Reduce a polyline to fewer points while preserving shape."""
    if len(points) < 3:
        return points
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

    All PDF mutation is delegated to ``AnnotationService``; this class only
    handles canvas preview rendering and coordinate translation.

    Parameters
    ----------
    ctx : AppContext
    annotation_service : AnnotationService
        Service used to write annotations to the PDF document.
    get_mode : callable → str
        Returns ``"pen"``, ``"line"``, ``"arrow"``, or ``"ellipse"``.
    get_stroke_rgb : callable → tuple
        Returns (r, g, b) 0-255.
    get_fill_rgb : callable → tuple | None
    get_width : callable → float
    get_opacity : callable → float   0.0–1.0
    on_committed : callable(page_idx: int, xref: int)
        Called after an annotation is successfully written so the caller can
        push an undo command and refresh rendering.
    """

    def __init__(
        self,
        ctx: "AppContext",
        annotation_service: "AnnotationService",
        get_mode,
        get_stroke_rgb,
        get_fill_rgb,
        get_width,
        get_opacity,
        on_committed,
    ) -> None:
        self._ctx          = ctx
        self._service      = annotation_service
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

    def activate(self) -> None:
        canvas = self._ctx.canvas
        canvas.bind("<Shift_L>",              self._on_shift_down, add="+")
        canvas.bind("<Shift_R>",              self._on_shift_down, add="+")
        canvas.bind("<KeyRelease-Shift_L>",   self._on_shift_up,   add="+")
        canvas.bind("<KeyRelease-Shift_R>",   self._on_shift_up,   add="+")

    def deactivate(self) -> None:
        self._drawing = False
        self._ctx.canvas.delete("draw_preview")
        canvas = self._ctx.canvas
        canvas.unbind("<Shift_L>")
        canvas.unbind("<Shift_R>")
        canvas.unbind("<KeyRelease-Shift_L>")
        canvas.unbind("<KeyRelease-Shift_R>")

    def on_click(self, cx: float, cy: float) -> None:
        self._drawing     = True
        self._start_cx    = cx
        self._start_cy    = cy
        self._pen_points  = [(cx, cy)]
        # Snapshot offsets so a mid-drag page change doesn't corrupt coords
        self._ox       = self._ctx.page_offset_x
        self._oy       = self._ctx.page_offset_y
        self._page_idx = self._ctx.current_page
        self._scale    = self._ctx.scale

    def on_drag(self, cx: float, cy: float) -> None:
        if not self._drawing:
            return
        if self._get_mode() == "pen":
            self._pen_points.append((cx, cy))
        self._redraw_preview(cx, cy)

    def on_release(self, cx: float, cy: float) -> None:
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

    def _fill_hex_or_empty(self) -> str:
        fill = self._get_fill()
        if fill is None:
            return ""
        r, g, b = fill
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

    def _redraw_preview(self, cx: float, cy: float) -> None:
        canvas = self._ctx.canvas
        canvas.delete("draw_preview")
        mode  = self._get_mode()
        color = self._stroke_hex()
        w     = max(1, self._get_width())
        sx, sy = self._start_cx, self._start_cy
        ecx, ecy = (
            self._snapped(sx, sy, cx, cy)
            if self._shift and mode != "pen"
            else (cx, cy)
        )

        if mode == "pen":
            pts = self._pen_points
            if len(pts) >= 2:
                flat = [coord for p in pts for coord in p]
                canvas.create_line(
                    *flat, fill=color, width=w,
                    smooth=True, splinesteps=12,
                    capstyle=tk.ROUND, joinstyle=tk.ROUND,
                    tags="draw_preview",
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
            canvas.create_oval(
                min(sx, ecx), min(sy, ecy),
                max(sx, ecx), max(sy, ecy),
                outline=color, fill=self._fill_hex_or_empty(), width=w,
                tags="draw_preview",
            )

    @staticmethod
    def _snapped(sx: float, sy: float, cx: float, cy: float) -> tuple[float, float]:
        """Snap end point to the nearest 45-degree angle from start."""
        dx, dy = cx - sx, cy - sy
        angle  = math.atan2(dy, dx)
        snap   = round(angle / (math.pi / 4)) * (math.pi / 4)
        dist   = math.hypot(dx, dy)
        return sx + dist * math.cos(snap), sy + dist * math.sin(snap)

    # ── coordinate helpers ────────────────────────────────────────────────────

    def _to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        """Convert canvas coords to PDF coords using offsets captured at drag start."""
        return (
            (cx - self._ox) / self._scale,
            (cy - self._oy) / self._scale,
        )

    def _annot_colors(self) -> tuple[tuple, tuple | None]:
        """Return (stroke_01, fill_01|None) in 0-1 float range for the service."""
        sr, sg, sb = self._get_stroke()
        stroke    = (sr / 255.0, sg / 255.0, sb / 255.0)
        fill_rgb  = self._get_fill()
        fill      = tuple(c / 255.0 for c in fill_rgb) if fill_rgb else None
        return stroke, fill

    # ── PDF commit (delegates to AnnotationService) ───────────────────────────

    def _commit_pen(self) -> None:
        pts = self._pen_points
        if len(pts) < 2:
            return

        simplified = _rdp(pts, epsilon=2.0)
        if len(simplified) < 2:
            simplified = [pts[0], pts[-1]]

        pdf_pts = [self._to_pdf(x, y) for x, y in simplified]

        doc = self._ctx.doc
        if not doc:
            return

        stroke, _ = self._annot_colors()
        try:
            xref = self._service.add_ink_annotation(
                doc, self._page_idx, pdf_pts,
                stroke=stroke,
                width=self._get_width(),
                opacity=self._get_opacity(),
            )
            self._on_committed(self._page_idx, xref)
        except Exception as ex:
            import tkinter.messagebox as mb
            mb.showerror("Draw Error", str(ex))

    def _commit_shape(self, cx: float, cy: float, mode: str) -> None:
        sx, sy = self._start_cx, self._start_cy
        if self._shift:
            cx, cy = self._snapped(sx, sy, cx, cy)

        doc = self._ctx.doc
        if not doc:
            return

        stroke, fill = self._annot_colors()
        try:
            if mode in ("line", "arrow"):
                p1 = self._to_pdf(sx, sy)
                p2 = self._to_pdf(cx, cy)
                xref = self._service.add_line_annotation(
                    doc, self._page_idx, p1, p2,
                    stroke=stroke,
                    width=self._get_width(),
                    opacity=self._get_opacity(),
                    arrow=(mode == "arrow"),
                )
            elif mode == "ellipse":
                px0, py0 = self._to_pdf(min(sx, cx), min(sy, cy))
                px1, py1 = self._to_pdf(max(sx, cx), max(sy, cy))
                if abs(px1 - px0) < 2 or abs(py1 - py0) < 2:
                    return   # too small, skip
                xref = self._service.add_circle_annotation(
                    doc, self._page_idx,
                    (px0, py0, px1, py1),
                    stroke=stroke,
                    fill=fill,
                    width=self._get_width(),
                    opacity=self._get_opacity(),
                )
            else:
                return
            self._on_committed(self._page_idx, xref)
        except Exception as ex:
            import tkinter.messagebox as mb
            mb.showerror("Draw Error", str(ex))

    # ── shift key tracking ────────────────────────────────────────────────────

    def _on_shift_down(self, event: tk.Event) -> None:
        self._shift = True

    def _on_shift_up(self, event: tk.Event) -> None:
        self._shift = False