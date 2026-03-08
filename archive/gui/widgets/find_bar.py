"""
FindBar — browser-style find bar that slides in above the status bar.

Owned by InteractivePDFEditor. Shown / hidden via show() / hide().
All logic lives in FindTool; this widget is pure presentation.
"""

import tkinter as tk
from src.gui.theme import PALETTE, FONT_UI, FONT_MONO, FONT_LABEL


class FindBar:
    """
    Compact find bar packed between the canvas area and the status bar.

    Parameters
    ----------
    parent : tk.Widget
        The root window (used for pack placement).
    on_search : callable(query: str, case_sensitive: bool)
        Called when the user submits a new query (Enter or Find button).
    on_next : callable()
        Called when the user clicks Next or presses F3 / Enter again.
    on_prev : callable()
        Called when the user clicks Prev or presses Shift+F3.
    on_close : callable()
        Called when the user clicks ✕ or presses Escape.
    """

    def __init__(self, parent, on_search, on_next, on_prev, on_close):
        self._on_search = on_search
        self._on_next   = on_next
        self._on_prev   = on_prev
        self._on_close  = on_close
        self._visible   = False

        self._bar = tk.Frame(
            parent,
            bg=PALETTE["bg_mid"],
            height=36,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        self._bar.pack_propagate(False)
        # Packed by show(); hidden by hide() — inserted just above status bar.

        self._query_var = tk.StringVar()
        self._case_var  = tk.BooleanVar(value=False)

        self._build()

    # ── public interface ──────────────────────────────────────────────────────

    def show(self) -> None:
        """Slide the bar in and focus the query entry."""
        if not self._visible:
            self._bar.pack(side=tk.BOTTOM, fill=tk.X)
            self._visible = True
        self._entry.focus_set()
        self._entry.select_range(0, tk.END)

    def hide(self) -> None:
        """Slide the bar out."""
        if self._visible:
            self._bar.pack_forget()
            self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    def update_status(self, current: int, total: int, page: int) -> None:
        """Update the hit-count label: '3 of 12  (page 4)'."""
        if total == 0:
            self._status_lbl.config(text="No results", fg=PALETTE["danger"])
        else:
            self._status_lbl.config(
                text=f"{current} of {total}  (page {page})",
                fg=PALETTE["success"],
            )

    def clear_status(self) -> None:
        self._status_lbl.config(text="", fg=PALETTE["fg_dim"])

    def get_query(self) -> str:
        return self._query_var.get()

    def get_case_sensitive(self) -> bool:
        return self._case_var.get()

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        bar = self._bar

        # Close button
        tk.Button(
            bar, text="✕", command=self._on_close,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["danger"],
            font=("Helvetica", 11), relief="flat", bd=0,
            padx=10, pady=0, cursor="hand2",
        ).pack(side=tk.LEFT)

        tk.Label(
            bar, text="Find:",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, padx=6,
        ).pack(side=tk.LEFT)

        # Query entry
        self._entry = tk.Entry(
            bar, textvariable=self._query_var,
            bg="#252535", fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            selectbackground=PALETTE["accent_dim"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["border"],
            font=FONT_UI, width=28,
        )
        self._entry.pack(side=tk.LEFT, padx=(0, 6), ipady=3)
        self._entry.bind("<Return>",       lambda e: self._submit())
        self._entry.bind("<Escape>",       lambda e: self._on_close())
        self._entry.bind("<F3>",           lambda e: self._on_next())
        self._entry.bind("<Shift-F3>",     lambda e: self._on_prev())

        # Case-sensitive toggle
        tk.Checkbutton(
            bar, text="Aa", variable=self._case_var,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            selectcolor=PALETTE["accent_dim"],
            activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2",
        ).pack(side=tk.LEFT, padx=(0, 8))

        # Prev / Next buttons
        for label, cmd, tip in [
            ("◀", self._on_prev, "Previous match  (Shift+F3)"),
            ("▶", self._on_next, "Next match  (F3 / Enter)"),
        ]:
            tk.Button(
                bar, text=label, command=cmd,
                bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                activebackground=PALETTE["accent_dim"],
                activeforeground=PALETTE["accent_light"],
                font=("Helvetica", 10), relief="flat", bd=0,
                padx=10, pady=2, cursor="hand2",
            ).pack(side=tk.LEFT, padx=2)

        # Status label
        self._status_lbl = tk.Label(
            bar, text="",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            font=FONT_MONO, padx=12,
        )
        self._status_lbl.pack(side=tk.LEFT)

    # ── internals ─────────────────────────────────────────────────────────────

    def _submit(self) -> None:
        """Enter pressed: new search if query changed, else next hit."""
        query = self._query_var.get().strip()
        if not query:
            return
        self._on_search(query, self._case_var.get())