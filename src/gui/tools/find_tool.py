"""
FindTool — cross-page text search and hit navigation.

This is not a canvas interaction tool in the radio-button sense; it runs
alongside whatever drawing tool is active and never intercepts mouse events.
It is instantiated once and driven entirely by the FindBar widget and the
Ctrl+F / Escape key bindings.

Workflow
--------
1. User presses Ctrl+F → FindBar slides in.
2. User types a query and presses Enter (or clicks Next).
3. FindTool.search() scans every page, collecting (page_idx, rect) pairs.
4. FindTool.goto_hit() navigates to the page containing the target hit,
   draws yellow highlight overlays on all hits for that page, and scrolls
   the canvas so the active hit is visible.
5. Next / Prev cycle through hits; wrapping around at both ends.
6. Escape (or clicking ✕) closes the bar and clears all overlays.

Tool-state keys published via ctx.set_tool_state()
---------------------------------------------------
STATE_RESULTS_UPDATED : tuple (current_1based: int, total: int, page_1based: int)
    Published after every goto_hit() call so the find bar can update its
    "3 of 12 (page 4)" label.

STATE_CLOSED : None
    Published when the tool is dismissed so the window can hide the bar
    and release the Escape binding.
"""

from src.gui.tools.base_tool import BaseTool

# Tool-state key constants
STATE_RESULTS_UPDATED = "find.results_updated"  # value: (current, total, page)
STATE_CLOSED          = "find.closed"           # value: None

# Overlay colours
_HIT_OUTLINE  = "#FFD700"   # gold border
_HIT_FILL     = "#FFFF00"   # yellow fill
_HIT_STIPPLE  = "gray50"
_ACTIVE_OUTLINE = "#FF6600" # orange border for the focused hit
_ACTIVE_FILL    = "#FFA500"


class FindTool:
    """
    Cross-page text search and hit navigation.

    Not a BaseTool subclass — it never handles canvas mouse events.
    Constructed once in _init_tools() and held at self._find_tool.
    """

    def __init__(self, ctx):
        self.ctx = ctx

        # All hits across all pages: list of (page_idx, (x0,y0,x1,y1))
        self._hits:        list[tuple[int, tuple]] = []
        self._current_idx: int                     = -1

        # Canvas overlay item IDs drawn on the current page
        self._overlays:    list[int] = []

        # The page index whose overlays are currently drawn
        self._overlay_page: int | None = None

    # ── public API ────────────────────────────────────────────────────────────

    def search(self, query: str, case_sensitive: bool = False) -> int:
        """
        Scan every page for *query* and collect hits.

        Does NOT navigate or draw overlays — call goto_hit() afterwards.
        Returns the total number of hits found.
        """
        self.clear_overlays()
        self._hits        = []
        self._current_idx = -1

        doc = self.ctx.doc
        if not doc or not query.strip():
            return 0

        for page_idx in range(doc.page_count):
            page = doc.get_page(page_idx)
            rects = page.search_text_quads(query, case_sensitive=case_sensitive)
            for rect in rects:
                self._hits.append((page_idx, rect))

        return len(self._hits)

    def goto_hit(self, idx: int) -> None:
        if not self._hits:
            return

        self._current_idx = idx % len(self._hits)
        target_page, _rect = self._hits[self._current_idx]

        # Invalidate the cache for the new active page before rendering
        if hasattr(self.ctx, "invalidate_cache"):
            self.ctx.invalidate_cache(target_page)

        if self.ctx.current_page != target_page:
            self.ctx.navigate_to_page(target_page)
        else:
            self.ctx.render()

        self._scroll_to_active()
        self._publish_state()

    def next_hit(self) -> None:
        """Advance to the next hit, wrapping around."""
        if self._hits:
            self.goto_hit(self._current_idx + 1)

    def prev_hit(self) -> None:
        """Go back to the previous hit, wrapping around."""
        if self._hits:
            self.goto_hit(self._current_idx - 1)

    def close(self) -> None:
        """Clear all overlays and notify the window to hide the bar."""
        self.clear_overlays()
        self._hits        = []
        self._current_idx = -1
        self.ctx.set_tool_state(STATE_CLOSED, None)

    def clear_overlays(self) -> None:
        # Trigger cache invalidation to wipe the highlights cleanly
        if self._overlay_page is not None:
            if hasattr(self.ctx, "invalidate_cache"):
                self.ctx.invalidate_cache(self._overlay_page)
            self._overlay_page = None
            self.ctx.render()

    def redraw_overlays(self) -> None:
        pass # Now baked into the image, canvas redrawing is not needed

    def _draw_overlays_for_page(self, page_idx: int) -> None:
        pass # Now baked into the image, canvas redrawing is not needed

    def get_highlight_rects_for_page(self, page_idx: int) -> tuple[list, list]:
        """Returns (active_hit_rects, inactive_hit_rects) for the image compositor."""
        active = []
        inactive = []
        self._overlay_page = page_idx
        for hit_idx, (p_idx, rect) in enumerate(self._hits):
            if p_idx != page_idx:
                continue
            if hit_idx == self._current_idx:
                active.append(rect)
            else:
                inactive.append(rect)
        return active, inactive

    @property
    def is_active(self) -> bool:
        """True when a search has been run and hits (possibly 0) exist."""
        return self._current_idx >= 0 or bool(self._hits)

    @property
    def total_hits(self) -> int:
        return len(self._hits)

    # ── internals ─────────────────────────────────────────────────────────────
    def _scroll_to_active(self) -> None:
        """Scroll the canvas so the active hit rect is visible."""
        if self._current_idx < 0 or not self._hits:
            return
        _, (x0, y0, x1, y1) = self._hits[self._current_idx]
        ox = self.ctx.page_offset_x
        oy = self.ctx.page_offset_y
        s  = self.ctx.scale

        # Centre of the hit in canvas coords
        cx = ox + (x0 + x1) / 2 * s
        cy = oy + (y0 + y1) / 2 * s

        canvas = self.ctx.canvas
        cw     = canvas.winfo_width()
        ch     = canvas.winfo_height()
        sr     = canvas.cget("scrollregion").split() if canvas.cget("scrollregion") else None
        if not sr or len(sr) < 4:
            return
        total_w = float(sr[2])
        total_h = float(sr[3])
        if total_w <= 0 or total_h <= 0:
            return

        canvas.xview_moveto(max(0.0, (cx - cw / 2) / total_w))
        canvas.yview_moveto(max(0.0, (cy - ch / 2) / total_h))

    def _publish_state(self) -> None:
        if not self._hits or self._current_idx < 0:
            return
        page_idx, _ = self._hits[self._current_idx]
        self.ctx.set_tool_state(
            STATE_RESULTS_UPDATED,
            (self._current_idx + 1, len(self._hits), page_idx + 1),
        )