"""
RedactTool — canvas interaction tool for text redaction.

Supports two workflows:

1. Draw mode (default)
   Drag a rubber-band on the canvas → release → immediately redact that rect.
   Overlaid with a semi-transparent red preview during the drag.

2. Search mode (triggered from the sidebar panel)
   Enter a search term → click "Find & Redact" → every hit on the current
   page is highlighted in red → user can confirm or cancel before committing.

Both workflows go through RedactCommand / BulkRedactCommand so undo works
exactly like every other destructive operation (disk-backed snapshot).
"""

import tkinter as tk
from tkinter import messagebox

from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE
from src.commands.redact import RedactCommand, BulkRedactCommand


# Semi-transparent redaction preview colour (canvas only — not burnt into PDF)
_PREVIEW_OUTLINE = "#FF2222"
_PREVIEW_FILL    = ""          # tk canvas rectangles can't do real alpha; use stipple
_PREVIEW_STIPPLE = "gray50"


class RedactTool(BaseTool):
    """
    Drag-to-redact + search-and-redact tool.

    Parameters
    ----------
    ctx : AppContext
    redaction_service : RedactionService
    get_fill_color : callable → tuple
        Returns the current fill colour as an RGB 0.0–1.0 tuple.
    get_replacement_text : callable → str
        Returns the replacement label (e.g. "[REDACTED]" or "").
    """

    MIN_DRAG_PX = 8

    def __init__(self, ctx, redaction_service, get_fill_color, get_replacement_text):
        super().__init__(ctx)
        self._service           = redaction_service
        self._get_fill          = get_fill_color
        self._get_replacement   = get_replacement_text

        # Draw-mode drag state
        self._drag_start: tuple | None  = None
        self._rubber_band: int | None   = None

        # Search-mode state
        # List of (x0, y0, x1, y1) PDF-space rects for pending hits
        self._pending_hits: list[tuple]  = []
        # Canvas item IDs for the red hit-highlight overlays
        self._hit_overlays: list[int]    = []

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self):
        self.ctx.canvas.config(cursor="crosshair")

    def deactivate(self):
        self._cancel_drag()
        self._clear_hit_overlays()

    # ── draw-mode events ──────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float):
        # If there are pending search hits, a click outside the confirm button
        # should do nothing — user must confirm or cancel via the sidebar.
        if self._pending_hits:
            return
        self._drag_start  = (canvas_x, canvas_y)
        self._rubber_band = None

    def on_drag(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None or self._pending_hits:
            return
        x0, y0 = self._drag_start
        if self._rubber_band is None:
            self._rubber_band = self.ctx.canvas.create_rectangle(
                x0, y0, canvas_x, canvas_y,
                outline=_PREVIEW_OUTLINE, width=2,
                fill="#FF0000", stipple=_PREVIEW_STIPPLE,
                tags="redact_preview",
            )
        else:
            self.ctx.canvas.coords(self._rubber_band, x0, y0, canvas_x, canvas_y)

    def on_release(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None or self._pending_hits:
            return

        x0, y0 = self._drag_start
        self._cancel_drag()

        if abs(canvas_x - x0) < self.MIN_DRAG_PX or abs(canvas_y - y0) < self.MIN_DRAG_PX:
            return

        px0, py0 = self._canvas_to_pdf(min(x0, canvas_x), min(y0, canvas_y))
        px1, py1 = self._canvas_to_pdf(max(x0, canvas_x), max(y0, canvas_y))
        rect = (px0, py0, px1, py1)

        if not messagebox.askyesno(
            "Confirm Redaction",
            "Permanently redact this region?\n\n"
            "This removes all underlying text, images, and graphics.\n"
            "The operation can be undone only before saving.",
            icon="warning",
        ):
            return

        cmd = RedactCommand(
            self._service, self.ctx.doc,
            self.ctx.current_page, rect,
            fill_color=self._get_fill(),
            replacement_text=self._get_replacement(),
        )
        try:
            cmd.execute()
            self.ctx.push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Redaction Error", str(ex))
            return

        self.ctx.flash_status("✓ Region redacted")
        self.ctx.render()

    # ── search-mode public API (called by sidebar) ────────────────────────────

    def find_hits(self, query: str, case_sensitive: bool = False) -> int:
        """
        Search the current page for *query*, draw red overlays on every hit,
        and stage them as pending hits waiting for confirmation.

        Returns the number of hits found (0 if nothing matched).
        """
        self._clear_hit_overlays()
        self._pending_hits = []

        if not query.strip() or not self.ctx.doc:
            return 0

        hits = self._service.find_text(
            self.ctx.doc,
            self.ctx.current_page,
            query,
            case_sensitive=case_sensitive,
        )
        if not hits:
            return 0

        self._pending_hits = hits
        self._draw_hit_overlays(hits)
        return len(hits)

    def confirm_redact_hits(self) -> bool:
        """
        Apply BulkRedactCommand for all pending hits.
        Returns True on success, False if there was nothing to redact or an error.
        """
        if not self._pending_hits:
            return False

        rects = list(self._pending_hits)
        self._clear_hit_overlays()
        self._pending_hits = []

        cmd = BulkRedactCommand(
            self._service, self.ctx.doc,
            self.ctx.current_page, rects,
            fill_color=self._get_fill(),
            replacement_text=self._get_replacement(),
        )
        try:
            cmd.execute()
            self.ctx.push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Redaction Error", str(ex))
            return False

        self.ctx.flash_status(f"✓ Redacted {len(rects)} match(es)")
        self.ctx.render()
        return True

    def cancel_hits(self):
        """Discard pending search hits without redacting."""
        self._clear_hit_overlays()
        self._pending_hits = []

    @property
    def has_pending_hits(self) -> bool:
        return bool(self._pending_hits)

    # ── internals ─────────────────────────────────────────────────────────────

    def _draw_hit_overlays(self, hits: list[tuple]):
        ox = self.ctx.page_offset_x
        oy = self.ctx.page_offset_y
        s  = self.ctx.scale
        for x0, y0, x1, y1 in hits:
            cx0 = ox + x0 * s
            cy0 = oy + y0 * s
            cx1 = ox + x1 * s
            cy1 = oy + y1 * s
            iid = self.ctx.canvas.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=_PREVIEW_OUTLINE, width=2,
                fill="#FF0000", stipple=_PREVIEW_STIPPLE,
                tags="redact_preview",
            )
            self._hit_overlays.append(iid)

    def _clear_hit_overlays(self):
        for iid in self._hit_overlays:
            try:
                self.ctx.canvas.delete(iid)
            except Exception:
                pass
        self._hit_overlays = []
        self.ctx.canvas.delete("redact_preview")

    def _cancel_drag(self):
        if self._rubber_band is not None:
            self.ctx.canvas.delete(self._rubber_band)
            self._rubber_band = None
        self._drag_start = None