"""
AppContext — lightweight namespace passed to all tool classes.

Tools receive this object at construction so they can reach shared application
state (canvas, document, current page, scale) and dispatch actions (push a
command, re-render, flash the status bar) without holding a reference to the
full InteractivePDFEditor class.

Tool-state protocol
-------------------
Tools that need to communicate richer state back to the sidebar (e.g. "I found
N search hits, show the confirm panel") use the two-method contract:

    ctx.set_tool_state(key, value)   # called by the tool
    ctx.on_tool_state_change         # set by the window to a callable

The window registers a single handler::

    self._ctx.on_tool_state_change = self._on_tool_state_change

and routes updates to the relevant sidebar panel by inspecting *key*. Tools
never reference sidebar widgets directly; the window never reaches into tool
internals to read state. The decoupling is intentional and must be preserved
as new tools are added.

Keys are plain strings by convention namespaced to the tool, e.g.:
    "redact.hits_found"     int   — number of search hits staged for redaction
    "redact.hits_cleared"   None  — pending hits were cancelled or committed

New tools should define their key constants at the top of their module.
"""

import tkinter as tk
from src.core.document import PDFDocument


class AppContext:
    """
    Lightweight namespace passed to tool classes so they can reach shared
    application state without holding a reference to the full editor class.
    """

    def __init__(self, editor: "InteractivePDFEditor"):
        self._editor = editor
        # Single callback wired by the window after construction.
        # Signature: on_tool_state_change(key: str, value: object) -> None
        self.on_tool_state_change = None

    # ── document / view state (read-only for tools) ───────────────────────────

    @property
    def canvas(self) -> tk.Canvas:
        return self._editor.canvas

    @property
    def doc(self) -> PDFDocument | None:
        return self._editor.doc

    @property
    def current_page(self) -> int:
        return self._editor.current_page_idx

    @property
    def scale(self) -> float:
        return self._editor.scale_factor

    @property
    def page_offset_x(self) -> float:
        return self._editor._page_offset_x

    @property
    def page_offset_y(self) -> float:
        return self._editor._page_offset_y

    # ── actions (tools call these to drive the window) ────────────────────────
    def invalidate_cache(self, page_idx: int = None) -> None:
            self._editor._cont_invalidate_cache(page_idx)

    def canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        return self._editor._canvas_to_pdf(cx, cy)

    def push_history(self, cmd):
        self._editor._push_history(cmd)

    def render(self):
        self._editor._render()

    def flash_status(self, message: str, color: str = None, duration_ms: int = 3000):
        self._editor._flash_status(message, color, duration_ms)

    def navigate_to_page(self, idx: int) -> None:
        self._editor._navigate_to(idx)

    # ── tool-state protocol ───────────────────────────────────────────────────

    def set_tool_state(self, key: str, value: object) -> None:
        """
        Publish a state change from a tool to the window/sidebar.

        The window routes the update by inspecting *key*. Tools must never
        call sidebar widget methods directly — all sidebar updates must flow
        through this method so the tool↔sidebar coupling stays in one place.

        Parameters
        ----------
        key : str
            Dot-namespaced identifier, e.g. ``"redact.hits_found"``.
        value : object
            The new state value. Semantics are key-specific; see each tool's
            module docstring for the full contract.
        """
        if self.on_tool_state_change is not None:
            self.on_tool_state_change(key, value)