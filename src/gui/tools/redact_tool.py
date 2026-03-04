"""
RedactTool — canvas interaction tool for text redaction.

Supports two workflows:

1. Draw mode (default)
   Drag a rubber-band on the canvas → release → an inline confirm bar appears
   on the canvas (no dialog) so the user clicks Confirm or Cancel without
   any focus-stealing that would break the drag cycle.

2. Search mode (triggered from the search bar / Ctrl+F)
   Searches ALL pages for a query.  Hits are stored as (page_idx, rect)
   pairs.  The "current" hit is shown in yellow; all others on the visible
   page are shown in purple.  Prev/Next buttons navigate through every hit,
   crossing page boundaries automatically.

   When the user is ready to redact, two options:
     • "Redact This" — redacts only the current (yellow) hit.
     • "Redact All"  — redacts every hit on every page.

Both draw-mode and search-mode redactions go through RedactCommand /
BulkRedactCommand, so undo works exactly like every other destructive
operation (disk-backed snapshot).
"""

import tkinter as tk
from tkinter import messagebox

from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE
from src.commands.redact import RedactCommand, BulkRedactCommand

# ── overlay colours ────────────────────────────────────────────────────────
_DRAW_OUTLINE    = "#FF2222"
_DRAW_STIPPLE    = "gray50"

_HIT_OUTLINE     = "#9B72CF"   # purple — non-current hits
_HIT_FILL        = "#7B3FBF"
_HIT_STIPPLE     = "gray25"

_CUR_OUTLINE     = "#FFD700"   # yellow — current (focused) hit
_CUR_FILL        = "#FFB800"
_CUR_STIPPLE     = "gray50"


class RedactTool(BaseTool):
    """
    Drag-to-redact + multi-page search-and-redact tool.

    Parameters
    ----------
    ctx : AppContext
    redaction_service : RedactionService
    get_fill_color : callable → tuple
        Returns the current fill colour as an RGB 0.0–1.0 tuple.
    get_replacement_text : callable → str
        Returns the replacement label (e.g. "[REDACTED]" or "").
    on_navigate_page : callable(int) → None
        Called when the tool needs the editor to jump to a different page.
    on_hit_changed : callable(current_idx, total) → None
        Called after every navigation step so the search bar can update
        its "N of M" counter and enable/disable arrows.
    """

    MIN_DRAG_PX = 8

    def __init__(
        self,
        ctx,
        redaction_service,
        get_fill_color,
        get_replacement_text,
        on_navigate_page=None,
        on_hit_changed=None,
    ):
        super().__init__(ctx)
        self._service           = redaction_service
        self._get_fill          = get_fill_color
        self._get_replacement   = get_replacement_text
        self._on_navigate_page  = on_navigate_page   # callable(page_idx)
        self._on_hit_changed    = on_hit_changed      # callable(cur, total)

        # Draw-mode drag state
        self._drag_start: tuple | None  = None
        self._rubber_band: int | None   = None

        # Pending draw-mode rect waiting for inline confirm
        self._pending_draw_rect: tuple | None = None
        self._confirm_overlay_ids: list[int]  = []

        # ── Multi-page search state ────────────────────────────────────────
        # List of (page_index, (x0, y0, x1, y1)) for every hit across all pages
        self._all_hits: list[tuple]    = []
        # Index into _all_hits that is currently "focused" (yellow)
        self._cur_hit_idx: int         = -1
        # Canvas overlay item IDs for the *current page only*
        self._hit_overlay_ids: list[int] = []

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self):
        self.ctx.canvas.config(cursor="crosshair")
        # Re-draw overlays for the current page when re-activating
        if self._all_hits:
            self._redraw_page_overlays()

    def deactivate(self):
        self._cancel_drag()
        self._cancel_draw_confirm()
        self._clear_page_overlays()

    # ── draw-mode events ──────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float):
        if self._pending_draw_rect is not None:
            return
        if self._all_hits:
            return
        self._drag_start  = (canvas_x, canvas_y)
        self._rubber_band = None

    def on_drag(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None or self._all_hits or self._pending_draw_rect is not None:
            return
        x0, y0 = self._drag_start
        if self._rubber_band is None:
            self._rubber_band = self.ctx.canvas.create_rectangle(
                x0, y0, canvas_x, canvas_y,
                outline=_DRAW_OUTLINE, width=2,
                fill="#FF0000", stipple=_DRAW_STIPPLE,
                tags="redact_preview",
            )
        else:
            self.ctx.canvas.coords(self._rubber_band, x0, y0, canvas_x, canvas_y)

    def on_release(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None or self._all_hits or self._pending_draw_rect is not None:
            return

        x0, y0          = self._drag_start
        self._drag_start = None

        if abs(canvas_x - x0) < self.MIN_DRAG_PX or abs(canvas_y - y0) < self.MIN_DRAG_PX:
            self._cancel_drag()
            return

        px0, py0 = self._canvas_to_pdf(min(x0, canvas_x), min(y0, canvas_y))
        px1, py1 = self._canvas_to_pdf(max(x0, canvas_x), max(y0, canvas_y))
        self._pending_draw_rect = (px0, py0, px1, py1)

        self._show_draw_confirm_overlay(
            min(x0, canvas_x), min(y0, canvas_y),
            max(x0, canvas_x), max(y0, canvas_y),
        )

    # ── inline draw-confirm overlay ───────────────────────────────────────────

    def _show_draw_confirm_overlay(self, cx0, cy0, cx1, cy1):
        c      = self.ctx.canvas
        bar_h  = 28
        bar_y  = cy1 + 6
        bar_cx = (cx0 + cx1) / 2

        bg_id = c.create_rectangle(
            bar_cx - 110, bar_y, bar_cx + 110, bar_y + bar_h,
            fill="#1C1C26", outline=_DRAW_OUTLINE, width=1,
            tags="redact_confirm_overlay",
        )
        lbl_id = c.create_text(
            bar_cx - 60, bar_y + bar_h / 2,
            text="⚠ Confirm redaction?",
            fill="#F87171", font=("Helvetica", 9, "bold"),
            anchor="center", tags="redact_confirm_overlay",
        )

        conf_frame = tk.Frame(c, bg="#B91C1C", cursor="hand2", relief="flat", bd=0)
        tk.Label(conf_frame, text="✓  Redact",
                 bg="#B91C1C", fg="#FFFFFF",
                 font=("Helvetica", 9, "bold"), padx=8, pady=4).pack()
        conf_frame.bind("<Button-1>", lambda e: self._confirm_draw_redact())
        conf_frame.winfo_children()[0].bind("<Button-1>", lambda e: self._confirm_draw_redact())
        conf_win = c.create_window(bar_cx + 42, bar_y + bar_h / 2,
                                   anchor="center", window=conf_frame,
                                   tags="redact_confirm_overlay")

        canc_frame = tk.Frame(c, bg="#252535", cursor="hand2", relief="flat", bd=0)
        tk.Label(canc_frame, text="✕  Cancel",
                 bg="#252535", fg="#8888AA",
                 font=("Helvetica", 9), padx=8, pady=4).pack()
        canc_frame.bind("<Button-1>", lambda e: self._cancel_draw_confirm())
        canc_frame.winfo_children()[0].bind("<Button-1>", lambda e: self._cancel_draw_confirm())
        canc_win = c.create_window(bar_cx - 52, bar_y + bar_h / 2,
                                   anchor="center", window=canc_frame,
                                   tags="redact_confirm_overlay")

        self._confirm_overlay_ids = [bg_id, lbl_id, conf_win, canc_win]

    def _confirm_draw_redact(self):
        rect = self._pending_draw_rect
        self._cancel_draw_confirm()
        if rect is None:
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

    def _cancel_draw_confirm(self):
        c = self.ctx.canvas
        for iid in self._confirm_overlay_ids:
            try:
                c.delete(iid)
            except Exception:
                pass
        c.delete("redact_confirm_overlay")
        self._confirm_overlay_ids = []
        self._pending_draw_rect   = None
        self._cancel_drag()

    # ── multi-page search public API ──────────────────────────────────────────

    def search_all_pages(self, query: str, case_sensitive: bool = False) -> int:
        """
        Search every page for *query*.  Populates self._all_hits and sets the
        current hit to the first hit on or after the currently visible page.

        Returns total number of hits across all pages.
        """
        self._clear_page_overlays()
        self._all_hits    = []
        self._cur_hit_idx = -1

        if not query.strip() or not self.ctx.doc:
            self._notify_hit_changed()
            return 0

        doc = self.ctx.doc
        for page_idx in range(doc.page_count):
            rects = self._service.find_text(
                doc, page_idx, query, case_sensitive=case_sensitive,
            )
            for r in rects:
                self._all_hits.append((page_idx, r))

        if not self._all_hits:
            self._notify_hit_changed()
            return 0

        # Start from the first hit on the current page, or the first hit overall
        current_page = self.ctx.current_page
        start_idx    = 0
        for i, (pg, _) in enumerate(self._all_hits):
            if pg >= current_page:
                start_idx = i
                break

        self._cur_hit_idx = start_idx
        self._go_to_current_hit(jump_page=True)
        return len(self._all_hits)

    def navigate_next(self):
        """Advance to the next hit (wraps around)."""
        if not self._all_hits:
            return
        self._cur_hit_idx = (self._cur_hit_idx + 1) % len(self._all_hits)
        self._go_to_current_hit(jump_page=True)

    def navigate_prev(self):
        """Go back to the previous hit (wraps around)."""
        if not self._all_hits:
            return
        self._cur_hit_idx = (self._cur_hit_idx - 1) % len(self._all_hits)
        self._go_to_current_hit(jump_page=True)

    def redact_current_hit(self) -> bool:
        """Redact only the currently focused hit."""
        if self._cur_hit_idx < 0 or not self._all_hits:
            return False
        page_idx, rect = self._all_hits[self._cur_hit_idx]
        # Remove from hit list before redacting so overlays stay consistent
        self._all_hits.pop(self._cur_hit_idx)
        self._cur_hit_idx = min(self._cur_hit_idx, len(self._all_hits) - 1)

        self._clear_page_overlays()

        cmd = RedactCommand(
            self._service, self.ctx.doc,
            page_idx, rect,
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

        self.ctx.flash_status("✓ Match redacted")
        self.ctx.render()

        # Re-draw remaining overlays
        if self._all_hits:
            self._go_to_current_hit(jump_page=True)
        else:
            self._notify_hit_changed()
        return True

    def redact_all_hits(self) -> bool:
        """Redact every hit across all pages in a single undoable step per page."""
        if not self._all_hits:
            return False

        # Group hits by page so we use one BulkRedactCommand per page
        from collections import defaultdict
        by_page: dict[int, list] = defaultdict(list)
        for page_idx, rect in self._all_hits:
            by_page[page_idx].append(rect)

        total = len(self._all_hits)
        self._clear_page_overlays()
        self._all_hits    = []
        self._cur_hit_idx = -1

        errors = []
        for page_idx, rects in sorted(by_page.items()):
            cmd = BulkRedactCommand(
                self._service, self.ctx.doc,
                page_idx, rects,
                fill_color=self._get_fill(),
                replacement_text=self._get_replacement(),
            )
            try:
                cmd.execute()
                self.ctx.push_history(cmd)
            except Exception as ex:
                cmd.cleanup()
                errors.append(f"Page {page_idx + 1}: {ex}")

        if errors:
            messagebox.showerror("Redaction Errors", "\n".join(errors))

        self.ctx.flash_status(f"✓ Redacted {total} match(es) across {len(by_page)} page(s)")
        self.ctx.render()
        self._notify_hit_changed()
        return True

    def cancel_search(self):
        """Clear all search state without redacting."""
        self._clear_page_overlays()
        self._all_hits    = []
        self._cur_hit_idx = -1
        self._notify_hit_changed()

    @property
    def has_search_hits(self) -> bool:
        return bool(self._all_hits)

    @property
    def current_hit_index(self) -> int:
        """0-based index of the focused hit, or -1 if none."""
        return self._cur_hit_idx

    @property
    def total_hits(self) -> int:
        return len(self._all_hits)

    # Keep old property name for compatibility with any callers
    @property
    def has_pending_hits(self) -> bool:
        return self.has_search_hits

    # ── internals ─────────────────────────────────────────────────────────────

    def _go_to_current_hit(self, jump_page: bool = False):
        """
        Navigate to the page of the current hit (if needed), redraw overlays,
        and scroll the canvas so the current hit is visible.
        """
        if self._cur_hit_idx < 0 or not self._all_hits:
            self._notify_hit_changed()
            return

        cur_page, cur_rect = self._all_hits[self._cur_hit_idx]

        # Jump to the hit's page if we're not already there
        if jump_page and cur_page != self.ctx.current_page:
            if self._on_navigate_page:
                self._on_navigate_page(cur_page)
            # _redraw_page_overlays will be called after the page renders via
            # activate(); we still call it here as a fallback.

        self._redraw_page_overlays()
        self._scroll_to_rect(cur_rect)
        self._notify_hit_changed()

    def _redraw_page_overlays(self):
        """
        Draw purple overlays for all hits on the current page, and a yellow
        overlay for the current (focused) hit if it's on this page.
        """
        self._clear_page_overlays()
        if not self._all_hits:
            return

        current_page = self.ctx.current_page
        ox = self.ctx.page_offset_x
        oy = self.ctx.page_offset_y
        s  = self.ctx.scale
        c  = self.ctx.canvas

        for i, (page_idx, (x0, y0, x1, y1)) in enumerate(self._all_hits):
            if page_idx != current_page:
                continue

            is_current = (i == self._cur_hit_idx)
            outline  = _CUR_OUTLINE  if is_current else _HIT_OUTLINE
            fill     = _CUR_FILL     if is_current else _HIT_FILL
            stipple  = _CUR_STIPPLE  if is_current else _HIT_STIPPLE
            tag      = "redact_cur"  if is_current else "redact_hit"

            cx0 = ox + x0 * s
            cy0 = oy + y0 * s
            cx1 = ox + x1 * s
            cy1 = oy + y1 * s
            iid = c.create_rectangle(
                cx0, cy0, cx1, cy1,
                outline=outline, width=2,
                fill=fill, stipple=stipple,
                tags=("redact_overlay", tag),
            )
            self._hit_overlay_ids.append(iid)

    def _clear_page_overlays(self):
        c = self.ctx.canvas
        for iid in self._hit_overlay_ids:
            try:
                c.delete(iid)
            except Exception:
                pass
        self._hit_overlay_ids = []
        c.delete("redact_overlay")

    def _scroll_to_rect(self, rect: tuple):
        """Scroll the canvas so *rect* (PDF-space) is roughly centred."""
        try:
            x0, y0, x1, y1 = rect
            ox = self.ctx.page_offset_x
            oy = self.ctx.page_offset_y
            s  = self.ctx.scale
            c  = self.ctx.canvas

            cy_center = oy + (y0 + y1) / 2 * s
            sr        = c.cget("scrollregion")
            if not sr:
                return
            sr_parts  = [float(v) for v in str(sr).split()]
            total_h   = sr_parts[3] if len(sr_parts) >= 4 else 1
            frac      = max(0.0, min(1.0, (cy_center - 150) / total_h))
            c.yview_moveto(frac)
        except Exception:
            pass

    def _notify_hit_changed(self):
        if self._on_hit_changed:
            self._on_hit_changed(self._cur_hit_idx, len(self._all_hits))

    def _cancel_drag(self):
        if self._rubber_band is not None:
            self.ctx.canvas.delete(self._rubber_band)
            self._rubber_band = None
        self._drag_start = None