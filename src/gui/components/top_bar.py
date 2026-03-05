"""
TopBar — single dark application toolbar.

Layout (left → right):
  ◼  File▾  Actions▾  |  ↩ Undo  ↪ Redo  |  🔍 Find  |  [title]  |
  Zoom − 65% + ↔ ⛶ ⟳  |  □ Page  ▤ Scroll  |  ◨  |  − □ ✕

File and Actions are tk.Menubutton dropdowns embedded in the dark bar.
No native OS menu bar is used.

Key fix: menus must be parented to their Menubutton (not the root window)
for the dropdown to appear correctly.
"""

from __future__ import annotations

import tkinter as tk

from src.gui.theme import (
    PALETTE, FONT_LABEL, FONT_MONO, FONT_SMALL, FONT_TITLE,
    PAD_S, PAD_M,
)
from src.gui.widgets.tooltip import Tooltip

_MENU_KW = dict(
    tearoff=0,
    font=("Helvetica Neue", 10),
)


def _mk_menu(parent: tk.Widget) -> tk.Menu:
    return tk.Menu(
        parent,
        bg=PALETTE["bg_panel"],
        fg=PALETTE["fg_primary"],
        activebackground=PALETTE["accent_dim"],
        activeforeground=PALETTE["accent_light"],
        **_MENU_KW,
    )


class TopBar:
    """
    Parameters
    ----------
    parent : tk.Widget
        Root window.
    callbacks : dict
        open, save, save_as,
        ocr_page, start_image_staging, open_merge_split,
        rotate_left, rotate_right, add_page, delete_page,
        undo, redo, toggle_search_bar,
        zoom_in, zoom_out, zoom_reset, zoom_fit_width, zoom_fit_page,
        set_single_mode, set_continuous_mode,
        toggle_inspector,
        wc_close, wc_minimize, wc_maximize.
    has_merge_split : bool
        Whether to show Merge / Split in the Actions menu.
    """

    def __init__(
        self,
        parent: tk.Widget,
        callbacks: dict,
        has_merge_split: bool = False,
    ) -> None:
        self._cb              = callbacks
        self._has_merge_split = has_merge_split

        self._zoom_label:     tk.Label      | None = None
        self._title_lbl:      tk.Label      | None = None
        self._btn_single:     tk.Button     | None = None
        self._btn_scroll:     tk.Button     | None = None
        self._btn_inspector:  tk.Button     | None = None
        self._recent_submenu: tk.Menu       | None = None

        # Kept for API compat (called by main_window but no longer a Menubutton)
        self._recent_mb: tk.Menubutton | None = None

        self.frame = self._build(parent)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self, parent: tk.Widget) -> tk.Frame:
        bar = tk.Frame(parent, bg=PALETTE["bg_mid"], height=48)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        # 3-column grid: left fixed | centre expands | right fixed
        bar.columnconfigure(0, weight=0)
        bar.columnconfigure(1, weight=1)
        bar.columnconfigure(2, weight=0)

        # ── Left cluster ──────────────────────────────────────────────────────
        left = tk.Frame(bar, bg=PALETTE["bg_mid"])
        left.grid(row=0, column=0, sticky="ns", padx=(PAD_M, 0))

        # Logo mark
        tk.Label(
            left, text="◼",
            bg=PALETTE["bg_mid"], fg=PALETTE["accent"],
            font=("Helvetica Neue", 14, "bold"),
        ).pack(side=tk.LEFT, padx=(0, PAD_S))

        # ── File Menubutton ───────────────────────────────────────────────────
        file_mb = tk.Menubutton(
            left, text="File",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=FONT_LABEL, relief="flat", bd=0,
            padx=PAD_M, pady=0, cursor="hand2",
            highlightthickness=0, direction="below",
        )
        file_mb.pack(side=tk.LEFT, fill=tk.Y)

        # Menu must be child of the Menubutton
        file_menu = _mk_menu(file_mb)
        file_menu.add_command(
            label="Open…",
            command=self._cb.get("open", lambda: None),
            accelerator="Ctrl+O")
        file_menu.add_command(
            label="Save",
            command=self._cb.get("save", lambda: None),
            accelerator="Ctrl+S")
        file_menu.add_command(
            label="Save As…",
            command=self._cb.get("save_as", lambda: None),
            accelerator="Ctrl+Shift+S")
        file_menu.add_separator()

        self._recent_submenu = _mk_menu(file_menu)
        self._recent_submenu.add_command(label="No recent files", state="disabled")
        file_menu.add_cascade(label="Recent Files", menu=self._recent_submenu)

        file_menu.add_separator()
        file_menu.add_command(
            label="Close",
            command=self._cb.get("wc_close", lambda: None))

        file_mb["menu"] = file_menu

        # ── Actions Menubutton ────────────────────────────────────────────────
        actions_mb = tk.Menubutton(
            left, text="Actions",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=FONT_LABEL, relief="flat", bd=0,
            padx=PAD_M, pady=0, cursor="hand2",
            highlightthickness=0, direction="below",
        )
        actions_mb.pack(side=tk.LEFT, fill=tk.Y)

        actions_menu = _mk_menu(actions_mb)
        actions_menu.add_command(
            label="OCR Current Page",
            command=self._cb.get("ocr_page", lambda: None))
        actions_menu.add_command(
            label="Images → PDF…",
            command=self._cb.get("start_image_staging", lambda: None))
        if self._has_merge_split:
            actions_menu.add_command(
                label="Merge / Split PDF…",
                command=self._cb.get("open_merge_split", lambda: None))
        actions_menu.add_separator()
        actions_menu.add_command(
            label="Rotate Page Left",
            command=self._cb.get("rotate_left", lambda: None))
        actions_menu.add_command(
            label="Rotate Page Right",
            command=self._cb.get("rotate_right", lambda: None))
        actions_menu.add_separator()
        actions_menu.add_command(
            label="Add Page",
            command=self._cb.get("add_page", lambda: None))
        actions_menu.add_command(
            label="Delete Page",
            command=self._cb.get("delete_page", lambda: None))

        actions_mb["menu"] = actions_menu

        # ── Divider then Undo / Redo / Find ───────────────────────────────────
        self._sep(left)

        Tooltip(self._tbtn(left, "↩ Undo", self._cb.get("undo")), "Undo  (Ctrl+Z)")
        Tooltip(self._tbtn(left, "↪ Redo", self._cb.get("redo")), "Redo  (Ctrl+Y)")

        self._sep(left)

        Tooltip(
            self._tbtn(left, "🔍 Find", self._cb.get("toggle_search_bar")),
            "Find & Redact  (Ctrl+F)")

        # ── Centre: document title ────────────────────────────────────────────
        centre = tk.Frame(bar, bg=PALETTE["bg_mid"])
        centre.grid(row=0, column=1, sticky="nsew")

        self._title_lbl = tk.Label(
            centre, text="PDF Editor",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            font=FONT_TITLE,
        )
        self._title_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Right cluster ─────────────────────────────────────────────────────
        right = tk.Frame(bar, bg=PALETTE["bg_mid"])
        right.grid(row=0, column=2, sticky="ns")

        # Zoom
        tk.Label(
            right, text="Zoom",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"], font=FONT_SMALL,
        ).pack(side=tk.LEFT, padx=(PAD_S, 2))
        Tooltip(self._tbtn(right, "−",  self._cb.get("zoom_out"),        padx=6), "Zoom out  (Ctrl+−)")
        self._zoom_label = tk.Label(
            right, text="100%",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            font=FONT_MONO, width=5,
        )
        self._zoom_label.pack(side=tk.LEFT)
        Tooltip(self._tbtn(right, "+",  self._cb.get("zoom_in"),         padx=6), "Zoom in  (Ctrl+=)")
        Tooltip(self._tbtn(right, "↔",  self._cb.get("zoom_fit_width"),  padx=6), "Fit to width  (Ctrl+1)")
        Tooltip(self._tbtn(right, "⛶",  self._cb.get("zoom_fit_page"),   padx=6), "Fit page  (Ctrl+2)")
        Tooltip(self._tbtn(right, "⟳",  self._cb.get("zoom_reset"),      padx=6), "Reset zoom  (Ctrl+0)")

        self._sep(right)

        # View-mode toggles
        self._btn_single = self._tbtn(right, "□ Page",   self._cb.get("set_single_mode"))
        self._btn_scroll = self._tbtn(right, "▤ Scroll", self._cb.get("set_continuous_mode"))
        Tooltip(self._btn_single, "Single page view")
        Tooltip(self._btn_scroll, "Continuous scroll view")

        self._sep(right)

        # Inspector toggle
        self._btn_inspector = tk.Button(
            right, text="◨",
            command=self._cb.get("toggle_inspector", lambda: None),
            bg=PALETTE["bg_hover"], fg=PALETTE["accent_light"],
            activebackground=PALETTE["accent_dim"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica Neue", 13), relief="flat", bd=0,
            padx=8, pady=0, cursor="hand2", highlightthickness=0,
        )
        self._btn_inspector.pack(side=tk.LEFT, fill=tk.Y)
        Tooltip(self._btn_inspector, "Show / Hide Inspector  (Ctrl+T)")

        self._sep(right)

        # Window chrome
        for txt, key, hover, fg in [
            ("−", "wc_minimize", PALETTE["bg_hover"], PALETTE["fg_secondary"]),
            ("□", "wc_maximize", PALETTE["bg_hover"], PALETTE["fg_secondary"]),
            ("✕", "wc_close",    "#C0635A",           "#E8E8E8"),
        ]:
            b = tk.Button(
                right, text=txt,
                command=self._cb.get(key, lambda: None),
                bg=PALETTE["bg_mid"], fg=fg,
                activebackground=hover, activeforeground="#FFFFFF",
                font=("Helvetica Neue", 11), relief="flat", bd=0,
                padx=14, pady=0, cursor="hand2", highlightthickness=0,
            )
            b.pack(side=tk.LEFT, fill=tk.Y)
            b.bind("<Enter>", lambda e, b=b, c=hover: b.config(bg=c))
            b.bind("<Leave>", lambda e, b=b: b.config(bg=PALETTE["bg_mid"]))

        # ── Drag to move window (needed since native title bar is removed) ─────
        for widget in (bar, centre, self._title_lbl):
            if widget:
                widget.bind("<ButtonPress-1>",   self._drag_start)
                widget.bind("<B1-Motion>",        self._drag_motion)

        return bar

    # ── public helpers ────────────────────────────────────────────────────────

    def set_title(self, text: str) -> None:
        if self._title_lbl:
            self._title_lbl.config(text=text)

    def set_zoom_label(self, text: str) -> None:
        if self._zoom_label:
            self._zoom_label.config(text=text)

    def set_recent_menu(self, menu: tk.Menu) -> None:
        """Repopulate the Recent Files sub-menu from the provided tk.Menu."""
        if not self._recent_submenu:
            return
        self._recent_submenu.delete(0, "end")
        try:
            last = menu.index("end")
        except tk.TclError:
            last = -1
        if last < 0:
            self._recent_submenu.add_command(label="No recent files", state="disabled")
            return
        for i in range(last + 1):
            try:
                entry_type = menu.type(i)
                if entry_type == "separator":
                    self._recent_submenu.add_separator()
                elif entry_type == "command":
                    lbl = menu.entrycget(i, "label")
                    cmd = menu.entrycget(i, "command")
                    fg  = menu.entrycget(i, "foreground")
                    kw = {"label": lbl, "command": cmd}
                    if fg:
                        kw["foreground"] = fg
                    self._recent_submenu.add_command(**kw)
            except tk.TclError:
                pass

    def update_view_mode_buttons(self, continuous: bool) -> None:
        if not self._btn_single or not self._btn_scroll:
            return
        if continuous:
            self._btn_single.config(fg=PALETTE["fg_dim"],       bg=PALETTE["bg_mid"])
            self._btn_scroll.config(fg=PALETTE["accent_light"], bg=PALETTE["bg_hover"])
        else:
            self._btn_single.config(fg=PALETTE["accent_light"], bg=PALETTE["bg_hover"])
            self._btn_scroll.config(fg=PALETTE["fg_dim"],       bg=PALETTE["bg_mid"])

    def set_inspector_active(self, visible: bool) -> None:
        if not self._btn_inspector:
            return
        if visible:
            self._btn_inspector.config(bg=PALETTE["bg_hover"], fg=PALETTE["accent_light"])
        else:
            self._btn_inspector.config(bg=PALETTE["bg_mid"],   fg=PALETTE["fg_dim"])

    # ── internal helpers ──────────────────────────────────────────────────────

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x_root - self.frame.winfo_toplevel().winfo_x()
        self._drag_y = event.y_root - self.frame.winfo_toplevel().winfo_y()

    def _drag_motion(self, event: tk.Event) -> None:
        win = self.frame.winfo_toplevel()
        win.geometry(f"+{event.x_root - self._drag_x}+{event.y_root - self._drag_y}")

    def _tbtn(self, parent: tk.Widget, text: str, cmd, padx: int = PAD_M) -> tk.Button:
        b = tk.Button(
            parent, text=text, command=cmd or (lambda: None),
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=FONT_LABEL, relief="flat", bd=0,
            padx=padx, pady=0, cursor="hand2", highlightthickness=0,
        )
        b.pack(side=tk.LEFT, fill=tk.Y)
        return b

    def _sep(self, parent: tk.Widget) -> None:
        tk.Frame(parent, bg=PALETTE["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=10, padx=PAD_S)