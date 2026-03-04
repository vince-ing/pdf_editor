"""
TopBar — custom application title bar with file actions, undo/redo,
zoom controls, view-mode toggles, and window chrome buttons.

Extracted from ``InteractivePDFEditor._build_topbar``.
"""

from __future__ import annotations

import tkinter as tk
from typing import TYPE_CHECKING

from src.gui.theme import (
    PALETTE, FONT_LABEL, FONT_MONO, FONT_SMALL, FONT_TITLE,
    PAD_S, PAD_M,
)
from src.gui.widgets.tooltip import Tooltip

if TYPE_CHECKING:
    from src.gui.components.canvas_area import CanvasArea


class TopBar:
    """
    Top application bar.

    Parameters
    ----------
    parent : tk.Widget
        The root window; the bar is packed into it.
    callbacks : dict
        Mapping of action name → callable.  Expected keys:
        ``open``, ``save``, ``save_as``, ``undo``, ``redo``,
        ``zoom_in``, ``zoom_out``, ``zoom_reset``,
        ``set_single_mode``, ``set_continuous_mode``,
        ``toggle_search_bar``, ``open_merge_split``, ``start_image_staging``,
        ``wc_close``, ``wc_minimize``, ``wc_maximize``.
    has_merge_split : bool
        Whether to show the Merge / Split button.
    """

    def __init__(
        self,
        parent: tk.Widget,
        callbacks: dict,
        has_merge_split: bool = False,
    ) -> None:
        self._parent         = parent
        self._cb             = callbacks
        self._has_merge_split = has_merge_split

        self._zoom_label: tk.Label | None      = None
        self._title_lbl:  tk.Label | None      = None
        self._btn_single: tk.Button | None     = None
        self._btn_scroll: tk.Button | None     = None
        self._recent_mb:  tk.Menubutton | None = None

        self.frame = self._build()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> tk.Frame:
        bar = tk.Frame(self._parent, bg=PALETTE["bg_mid"], height=48)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        # ── Far right: window chrome ──────────────────────────────────────────
        wctrl = tk.Frame(bar, bg=PALETTE["bg_mid"])
        wctrl.pack(side=tk.RIGHT, fill=tk.Y)

        def _wc_btn(txt, cmd, hover_color, text_color=PALETTE["fg_secondary"]):
            b = tk.Button(
                wctrl, text=txt, command=cmd,
                bg=PALETTE["bg_mid"], fg=text_color,
                activebackground=hover_color, activeforeground="#FFFFFF",
                font=("Helvetica Neue", 11), relief="flat", bd=0,
                padx=14, pady=0, cursor="hand2", highlightthickness=0,
            )
            b.pack(side=tk.LEFT, fill=tk.Y)
            b.bind("<Enter>", lambda e, b=b, c=hover_color: b.config(bg=c))
            b.bind("<Leave>", lambda e, b=b: b.config(bg=PALETTE["bg_mid"]))
            return b

        _wc_btn("✕", self._cb.get("wc_close",    lambda: None), "#C0635A", "#E8E8E8")
        _wc_btn("□", self._cb.get("wc_maximize",  lambda: None), PALETTE["bg_hover"])
        _wc_btn("−", self._cb.get("wc_minimize",  lambda: None), PALETTE["bg_hover"])

        # ── Left cluster ──────────────────────────────────────────────────────
        left = tk.Frame(bar, bg=PALETTE["bg_mid"])
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(PAD_M, 0))

        tk.Label(
            left, text="◼",
            bg=PALETTE["bg_mid"], fg=PALETTE["accent"],
            font=("Helvetica Neue", 14, "bold"),
        ).pack(side=tk.LEFT, padx=(0, PAD_S))

        for label, key, tip in [
            ("Open",    "open",    "Open PDF  (Ctrl+O)"),
            ("Save",    "save",    "Save  (Ctrl+S)"),
            ("Save As", "save_as", "Save As  (Ctrl+Shift+S)"),
        ]:
            Tooltip(self._topbar_btn(left, label, self._cb.get(key, lambda: None)), tip)

        # Recent files chevron
        self._recent_mb = tk.Menubutton(
            left, text="▾",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica Neue", 9), relief="flat", bd=0,
            padx=4, pady=0, cursor="hand2", highlightthickness=0,
        )
        self._recent_mb.pack(side=tk.LEFT)
        Tooltip(self._recent_mb, "Recent files")

        self._sep(left, "v")

        Tooltip(self._topbar_btn(left, "↩ Undo", self._cb.get("undo", lambda: None)), "Undo  (Ctrl+Z)")
        Tooltip(self._topbar_btn(left, "↪ Redo", self._cb.get("redo", lambda: None)), "Redo  (Ctrl+Y)")

        # ── Centre: document title ────────────────────────────────────────────
        self._title_lbl = tk.Label(
            bar, text="PDF Editor",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            font=FONT_TITLE,
        )
        self._title_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Right cluster ─────────────────────────────────────────────────────
        right = tk.Frame(bar, bg=PALETTE["bg_mid"])
        right.pack(side=tk.RIGHT, fill=tk.Y)

        if self._has_merge_split:
            Tooltip(
                self._topbar_btn(right, "Merge / Split",
                                 self._cb.get("open_merge_split", lambda: None)),
                "Merge or split PDF files",
            )
        Tooltip(
            self._topbar_btn(right, "Images → PDF",
                             self._cb.get("start_image_staging", lambda: None)),
            "Combine images into a PDF",
        )
        Tooltip(
            self._topbar_btn(right, "🔍 Find",
                             self._cb.get("toggle_search_bar", lambda: None)),
            "Find & Redact text  (Ctrl+F)",
        )

        self._sep(right, "v")

        # Zoom
        tk.Label(
            right, text="Zoom",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"], font=FONT_SMALL,
        ).pack(side=tk.LEFT, padx=(PAD_S, 2))
        Tooltip(self._topbar_btn(right, "−", self._cb.get("zoom_out",   lambda: None), padx=6), "Zoom out  (Ctrl+−)")
        self._zoom_label = tk.Label(
            right, text="100%",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            font=FONT_MONO, width=5,
        )
        self._zoom_label.pack(side=tk.LEFT)
        Tooltip(self._topbar_btn(right, "+", self._cb.get("zoom_in",    lambda: None), padx=6), "Zoom in  (Ctrl+=)")
        Tooltip(self._topbar_btn(right, "⟳", self._cb.get("zoom_reset", lambda: None), padx=6), "Reset zoom  (Ctrl+0)")
        Tooltip(self._topbar_btn(right, "↔", self._cb.get("zoom_fit_width", lambda: None), padx=6), "Fit to width  (Ctrl+1)")
        Tooltip(self._topbar_btn(right, "⛶", self._cb.get("zoom_fit_page",  lambda: None), padx=6), "Fit page  (Ctrl+2)")

        self._sep(right, "v")

        # View-mode toggles
        self._btn_single = self._topbar_btn(
            right, "□ Page", self._cb.get("set_single_mode", lambda: None))
        self._btn_scroll = self._topbar_btn(
            right, "▤ Scroll", self._cb.get("set_continuous_mode", lambda: None))
        Tooltip(self._btn_single, "Single page view")
        Tooltip(self._btn_scroll, "Continuous scroll view")

        return bar

    # ── public update helpers ─────────────────────────────────────────────────

    def set_title(self, text: str) -> None:
        if self._title_lbl:
            self._title_lbl.config(text=text)

    def set_zoom_label(self, text: str) -> None:
        if self._zoom_label:
            self._zoom_label.config(text=text)

    def set_recent_menu(self, menu: tk.Menu) -> None:
        if self._recent_mb:
            self._recent_mb.config(menu=menu)

    def update_view_mode_buttons(self, continuous: bool) -> None:
        if not self._btn_single or not self._btn_scroll:
            return
        if continuous:
            self._btn_single.config(fg=PALETTE["fg_dim"],       bg=PALETTE["bg_mid"])
            self._btn_scroll.config(fg=PALETTE["accent_light"], bg=PALETTE["bg_hover"])
        else:
            self._btn_single.config(fg=PALETTE["accent_light"], bg=PALETTE["bg_hover"])
            self._btn_scroll.config(fg=PALETTE["fg_dim"],       bg=PALETTE["bg_mid"])

    # ── internal helpers ──────────────────────────────────────────────────────

    def _topbar_btn(
        self,
        parent: tk.Widget,
        text: str,
        cmd,
        padx: int = PAD_M,
    ) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=cmd,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=FONT_LABEL, relief="flat", bd=0,
            padx=padx, pady=0,
            cursor="hand2", highlightthickness=0,
        )
        btn.pack(side=tk.LEFT, fill=tk.Y)
        return btn

    def _sep(self, parent: tk.Widget, orient: str = "v") -> None:
        bg = PALETTE["border"]
        if orient == "v":
            f = tk.Frame(parent, bg=bg, width=1)
            f.pack(side=tk.LEFT, fill=tk.Y, pady=10, padx=PAD_S)
        else:
            f = tk.Frame(parent, bg=bg, height=1)
            f.pack(fill=tk.X)