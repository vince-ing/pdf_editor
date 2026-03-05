"""
IconToolbar — thin vertical tool-selection strip on the left edge of the window.

Strictly canvas interaction tools only.  Page-level actions (rotate, add,
delete, OCR) have been removed — they live in the native Tools menu and in
the thumbnail right-click context menu.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from src.gui.theme import (
    PALETTE, FONT_LABEL,
    ICON_BAR_W, PAD_M, PAD_S,
)
from src.gui.widgets.tooltip import Tooltip

if TYPE_CHECKING:
    pass


# Tool definitions: (internal_name, icon_char, tooltip, group)
TOOL_DEFINITIONS = [
    ("__sep__", None, "Selection",          None),
    ("select_text",  "⬚",  "Select Text  — click or drag to copy text",   "select"),
    ("__sep__", None, "Markup",             None),
    ("highlight",    "▐",  "Highlight  — drag to mark a region",           "markup"),
    ("rect_annot",   "▭",  "Rectangle  — drag to draw a box annotation",   "markup"),
    ("draw",         "✏",  "Draw  — freehand pen, lines, arrows, shapes",  "markup"),
    ("redact",       "⬛",  "Redact  — permanently remove content",         "markup"),
    ("__sep__", None, "Insert / Extract",   None),
    ("text",         "T",  "Add Text  — click to place a text box",        "insert"),
    ("insert_image", "⊞",  "Insert Image  — choose then drag to place",    "insert"),
    ("extract",      "⇥",  "Extract Image  — click an image to save it",   "insert"),
]

# Single-key shortcut → tool name
TOOL_KEY_MAP: dict[str, str] = {
    "v": "select_text",
    "t": "text",
    "h": "highlight",
    "r": "rect_annot",
    "d": "draw",
    "x": "redact",
    "i": "insert_image",
    "e": "extract",
}


class IconToolbar:
    """
    Left vertical icon strip — canvas tools only.

    Parameters
    ----------
    parent : tk.Widget
        Body frame that contains the toolbar, canvas, and right panel.
    on_tool_select : callable(tool_name: str)
        Called when the user clicks a tool button.
    page_action_callbacks : dict
        Kept for API compatibility; ignored (actions moved to menus).
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_tool_select,
        page_action_callbacks: dict | None = None,
    ) -> None:
        self._on_tool_select = on_tool_select
        self._icon_btns: dict[str, tk.Button] = {}
        self._active_tool    = ""

        self.frame = self._build(parent)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self, parent: tk.Widget) -> tk.Frame:
        bar = tk.Frame(
            parent, bg=PALETTE["bg_panel"],
            width=ICON_BAR_W, highlightthickness=0,
        )
        bar.pack(side=tk.LEFT, fill=tk.Y)
        bar.pack_propagate(False)

        tk.Frame(bar, bg=PALETTE["bg_panel"], height=PAD_M).pack()

        _key_for = {v: k.upper() for k, v in TOOL_KEY_MAP.items()}

        for name, icon, tip, _group in TOOL_DEFINITIONS:
            if name == "__sep__":
                tk.Frame(bar, bg=PALETTE["border"], height=1).pack(
                    fill=tk.X, padx=8, pady=(PAD_M, 2))
                tk.Label(
                    bar, text=icon,
                    bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                    font=("Helvetica Neue", 7), anchor="center",
                ).pack(fill=tk.X)
                continue

            key_hint  = f"  [{_key_for.get(name, '')}]" if name in _key_for else ""
            full_tip  = tip + key_hint

            btn = tk.Button(
                bar,
                text=icon,
                command=lambda n=name: self._on_tool_select(n),
                bg=PALETTE["bg_panel"],
                fg=PALETTE["fg_secondary"],
                activebackground=PALETTE["accent_subtle"],
                activeforeground=PALETTE["accent_light"],
                font=("Helvetica Neue", 15),
                relief="flat", bd=0,
                width=2, pady=PAD_S,
                cursor="hand2", highlightthickness=0,
            )
            btn.pack(fill=tk.X, padx=4, pady=1)
            btn.bind("<Enter>", lambda e, b=btn, n=name: self._icon_hover(b, n, True))
            btn.bind("<Leave>", lambda e, b=btn, n=name: self._icon_hover(b, n, False))
            self._icon_btns[name] = btn
            Tooltip(btn, full_tip)

        # Bottom spacer (no page-action strip)
        tk.Frame(bar, bg=PALETTE["bg_panel"]).pack(fill=tk.BOTH, expand=True)
        tk.Frame(bar, bg=PALETTE["bg_panel"], height=PAD_M).pack()

        return bar

    # ── public helpers ────────────────────────────────────────────────────────

    def set_active_tool(self, tool_name: str) -> None:
        """Highlight the active tool button and de-highlight all others."""
        self._active_tool = tool_name
        for name, btn in self._icon_btns.items():
            if name == tool_name:
                btn.configure(bg=PALETTE["accent_subtle"], fg=PALETTE["accent_light"])
            else:
                btn.configure(bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"])

    # ── internal helpers ──────────────────────────────────────────────────────

    def _icon_hover(self, btn: tk.Button, name: str, entering: bool) -> None:
        """Hover highlight — don't override the active-tool colour."""
        if name == self._active_tool:
            return
        if entering:
            btn.config(bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"])
        else:
            btn.config(bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"])