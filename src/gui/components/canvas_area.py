"""
CanvasArea — the central PDF viewport with scrollbars and an inline
Find & Redact search bar that slides in above the canvas.

Extracted from ``InteractivePDFEditor._build_canvas_area``.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from src.gui.theme import PALETTE, FONT_LABEL, FONT_UI, FONT_MONO

if TYPE_CHECKING:
    pass


class CanvasArea:
    """
    Central canvas area.

    Parameters
    ----------
    parent : tk.Widget
        The body frame; canvas is packed into it.
    canvas_callbacks : dict
        Event handler callables.  Expected keys:
        ``on_click``, ``on_drag``, ``on_release``, ``on_mousewheel``,
        ``on_ctrl_scroll``, ``on_motion``, ``on_configure``.
    search_bar_callbacks : dict
        Callables for the inline search bar.  Expected keys:
        ``on_find``, ``on_next``, ``on_prev``, ``on_redact_one``,
        ``on_redact_all``, ``on_close``.
    """

    def __init__(
        self,
        parent: tk.Widget,
        canvas_callbacks: dict,
        search_bar_callbacks: dict,
    ) -> None:
        self._cc  = canvas_callbacks
        self._sc  = search_bar_callbacks

        # Widgets made available to the orchestrator
        self.canvas: tk.Canvas
        self.v_scroll: ttk.Scrollbar
        self.h_scroll: ttk.Scrollbar

        # Search-bar state widgets
        self._sb_entry: tk.Entry
        self._sb_case_var   = tk.BooleanVar(value=False)
        self._sb_query_var  = tk.StringVar()
        self._sb_hit_lbl:   tk.Label
        self._sb_prev_btn:  tk.Button
        self._sb_next_btn:  tk.Button
        self._sb_redact_one_btn: tk.Button
        self._sb_redact_all_btn: tk.Button
        self._search_bar_frame: tk.Frame
        self._search_bar_visible = False

        self.frame = self._build(parent)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self, parent: tk.Widget) -> tk.Frame:
        frame = tk.Frame(parent, bg=PALETTE["bg_dark"])
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._build_search_bar(frame)
        self._build_scrolled_canvas(frame)

        return frame

    def _build_search_bar(self, parent: tk.Widget) -> None:
        bar = tk.Frame(
            parent, bg=PALETTE["bg_mid"], height=44,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        self._search_bar_frame = bar
        # Hidden until show_search_bar() is called.

        def _sb_btn(p, text, cmd, **kw):
            defaults = dict(
                bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                activebackground=PALETTE["accent_dim"],
                font=FONT_LABEL, relief="flat", bd=0,
                padx=8, pady=4, cursor="hand2", highlightthickness=0,
            )
            defaults.update(kw)
            return tk.Button(p, text=text, command=cmd, **defaults)

        # Close
        _sb_btn(bar, "✕", self._sc.get("on_close", lambda: None),
                bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
                font=("Helvetica Neue", 11), padx=10).pack(side=tk.RIGHT)

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=8)

        self._sb_redact_all_btn = tk.Button(
            bar, text="⬛ Redact All",
            command=self._sc.get("on_redact_all", lambda: None),
            bg=PALETTE["danger"], fg="#0F0F13",
            activebackground="#A05050",
            font=("Helvetica Neue", 9, "bold"), relief="flat", bd=0,
            padx=10, pady=4, cursor="hand2",
            state=tk.DISABLED, highlightthickness=0,
        )
        self._sb_redact_all_btn.pack(side=tk.RIGHT, padx=(0, 4))

        self._sb_redact_one_btn = tk.Button(
            bar, text="Redact This",
            command=self._sc.get("on_redact_one", lambda: None),
            bg="#7B2020", fg="#FFCCCC",
            activebackground="#9B3030",
            font=FONT_LABEL, relief="flat", bd=0,
            padx=8, pady=4, cursor="hand2",
            state=tk.DISABLED, highlightthickness=0,
        )
        self._sb_redact_one_btn.pack(side=tk.RIGHT, padx=(0, 4))

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=8)

        self._sb_hit_lbl = tk.Label(
            bar, text="",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            font=FONT_MONO, padx=8, width=18, anchor="w",
        )
        self._sb_hit_lbl.pack(side=tk.RIGHT)

        self._sb_next_btn = _sb_btn(bar, "▶",
                                    self._sc.get("on_next", lambda: None),
                                    state=tk.DISABLED)
        self._sb_next_btn.pack(side=tk.RIGHT, padx=(0, 2))

        self._sb_prev_btn = _sb_btn(bar, "◀",
                                    self._sc.get("on_prev", lambda: None),
                                    state=tk.DISABLED)
        self._sb_prev_btn.pack(side=tk.RIGHT, padx=(0, 2))

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=8)

        tk.Label(
            bar, text="🔍 Find & Redact:",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, padx=8,
        ).pack(side=tk.LEFT)

        self._sb_entry = tk.Entry(
            bar, textvariable=self._sb_query_var,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["accent"],
            width=28, font=FONT_UI,
        )
        self._sb_entry.pack(side=tk.LEFT, padx=(0, 6), ipady=4)
        self._sb_entry.bind("<Return>", lambda e: self._sc.get("on_find", lambda: None)())
        self._sb_entry.bind("<Escape>", lambda e: self._sc.get("on_close", lambda: None)())

        tk.Checkbutton(
            bar, text="Aa", variable=self._sb_case_var,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            selectcolor=PALETTE["accent_dim"],
            activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2", highlightthickness=0,
        ).pack(side=tk.LEFT, padx=(0, 6))

        _sb_btn(bar, "Search All Pages",
                self._sc.get("on_find", lambda: None)).pack(side=tk.LEFT, padx=(0, 4))

    def _build_scrolled_canvas(self, parent: tk.Widget) -> None:
        self.v_scroll = ttk.Scrollbar(parent, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scroll = ttk.Scrollbar(parent, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(
            parent, bg=PALETTE["canvas_bg"],
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        cc = self._cc
        self.canvas.bind("<Button-1>",          cc.get("on_click",      lambda e: None))
        self.canvas.bind("<B1-Motion>",          cc.get("on_drag",       lambda e: None))
        self.canvas.bind("<ButtonRelease-1>",    cc.get("on_release",    lambda e: None))
        self.canvas.bind("<MouseWheel>",         cc.get("on_mousewheel", lambda e: None))
        self.canvas.bind("<Button-4>",           cc.get("on_mousewheel", lambda e: None))
        self.canvas.bind("<Button-5>",           cc.get("on_mousewheel", lambda e: None))
        self.canvas.bind("<Control-MouseWheel>", cc.get("on_ctrl_scroll",lambda e: None))
        self.canvas.bind("<Control-Button-4>",   cc.get("on_ctrl_scroll",lambda e: None))
        self.canvas.bind("<Control-Button-5>",   cc.get("on_ctrl_scroll",lambda e: None))
        self.canvas.bind("<Motion>",             cc.get("on_motion",     lambda e: None))
        self.canvas.bind("<Configure>",          cc.get("on_configure",  lambda e: None))

    # ── search-bar public API ─────────────────────────────────────────────────

    def show_search_bar(self) -> None:
        if not self._search_bar_visible:
            self._search_bar_frame.pack(side=tk.TOP, fill=tk.X, before=self.canvas)
            self._search_bar_visible = True
        self._sb_entry.focus_set()
        self._sb_entry.select_range(0, tk.END)

    def hide_search_bar(self) -> None:
        if self._search_bar_visible:
            self._search_bar_frame.pack_forget()
            self._search_bar_visible = False

    @property
    def search_bar_visible(self) -> bool:
        return self._search_bar_visible

    @property
    def search_query(self) -> str:
        return self._sb_query_var.get().strip()

    @property
    def search_case_sensitive(self) -> bool:
        return self._sb_case_var.get()

    def update_hit_display(
        self,
        cur_idx: int,
        total: int,
        page_label: str = "",
    ) -> None:
        """Update the search-bar hit counter and button states."""
        if total == 0 or cur_idx < 0:
            self._sb_hit_lbl.config(text="No matches", fg=PALETTE["fg_dim"])
            for b in (self._sb_prev_btn, self._sb_next_btn,
                      self._sb_redact_one_btn, self._sb_redact_all_btn):
                b.config(state=tk.DISABLED)
            return

        self._sb_hit_lbl.config(
            text=f"{cur_idx + 1} of {total}  ({page_label})",
            fg=PALETTE["fg_primary"],
        )
        can_nav = total > 1
        self._sb_prev_btn.config(state=tk.NORMAL if can_nav else tk.DISABLED)
        self._sb_next_btn.config(state=tk.NORMAL if can_nav else tk.DISABLED)
        self._sb_redact_one_btn.config(state=tk.NORMAL)
        self._sb_redact_all_btn.config(state=tk.NORMAL)

    def clear_hit_display(self) -> None:
        self._sb_hit_lbl.config(text="")
        for b in (self._sb_prev_btn, self._sb_next_btn,
                  self._sb_redact_one_btn, self._sb_redact_all_btn):
            b.config(state=tk.DISABLED)