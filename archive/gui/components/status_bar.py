"""
StatusBar — thin bar at the bottom of the window showing tool name, cursor
coordinates, page dimensions, action feedback, and zoom level.

Extracted from ``InteractivePDFEditor._build_statusbar``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from src.gui.theme import PALETTE, FONT_MONO


class StatusBar:
    """
    Bottom status bar.

    Parameters
    ----------
    parent : tk.Widget
        Root window; the bar is packed into the bottom of it.
    """

    def __init__(self, parent: tk.Widget) -> None:
        self._flash_after_id: str | None = None
        self._parent = parent
        self.frame   = self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> tk.Frame:
        bar = tk.Frame(self._parent, bg=PALETTE["shadow"], height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        def sep() -> None:
            tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
                side=tk.LEFT, fill=tk.Y, pady=4)

        self._st_tool = tk.Label(
            bar, text="Tool: Text",
            bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
            font=FONT_MONO, padx=10,
        )
        self._st_tool.pack(side=tk.LEFT)
        sep()

        self._st_coords = tk.Label(
            bar, text="x: —    y: —",
            bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
            font=FONT_MONO, padx=10,
        )
        self._st_coords.pack(side=tk.LEFT)
        sep()

        self._st_size = tk.Label(
            bar, text="",
            bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
            font=FONT_MONO, padx=10,
        )
        self._st_size.pack(side=tk.LEFT)
        sep()

        self._st_action = tk.Label(
            bar, text="",
            bg=PALETTE["shadow"], fg=PALETTE["success"],
            font=FONT_MONO, padx=10,
        )
        self._st_action.pack(side=tk.LEFT)

        # ADDED: Progress Bar (hidden by default)
        self._progress_bar = ttk.Progressbar(
            bar, orient=tk.HORIZONTAL, length=150, mode='indeterminate'
        )

        self._st_zoom = tk.Label(
            bar, text="",
            bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
            font=FONT_MONO, padx=10,
        )
        self._st_zoom.pack(side=tk.RIGHT)

        return bar

    # ── public update helpers ─────────────────────────────────────────────────

    def set_tool(self, tool_name: str) -> None:
        self._st_tool.config(text=f"Tool: {tool_name.replace('_', ' ').title()}")

    def set_coords(self, x: float, y: float) -> None:
        self._st_coords.config(text=f"x: {x:6.1f}   y: {y:6.1f}")

    def set_page_size(self, text: str) -> None:
        self._st_size.config(text=text)

    def set_zoom(self, text: str) -> None:
        self._st_zoom.config(text=text)

    def flash(
        self,
        message: str,
        color: str | None = None,
        duration_ms: int = 3000,
    ) -> None:
        """Show a transient action message that auto-clears after *duration_ms*."""
        if color is None:
            color = PALETTE["success"]
        self._st_action.config(text=message, fg=color)
        if self._flash_after_id:
            self._parent.after_cancel(self._flash_after_id)
        self._flash_after_id = self._parent.after(
            duration_ms, lambda: self._st_action.config(text=""))

    # ADDED: Background task UI methods
    def show_progress(self, message: str = "Processing...") -> None:
        if self._flash_after_id:
            self._parent.after_cancel(self._flash_after_id)
        self._st_action.config(text=message, fg=PALETTE["accent_light"])
        self._progress_bar.pack(side=tk.RIGHT, padx=10)
        self._progress_bar.start(10)

    def hide_progress(self, finish_message: str = "Done") -> None:
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        self.flash(finish_message)