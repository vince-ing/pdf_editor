"""
RightPanel — tabbed inspector panel on the right edge of the window.

Contains:
  • Pages tab  — sub-tabbed:
      – Thumbnails  (ThumbnailPanel, drag-to-reorder, context menus)
      – Bookmarks   (TocPanel, full outline editor)
  • Properties tab — context-sensitive tool options

The TOC sub-tab uses a nested ttk.Notebook inside the Pages outer tab so the
canvas area is not squeezed by a third full-height panel.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, colorchooser
from typing import TYPE_CHECKING

from src.gui.theme import (
    PALETTE, FONT_UI, FONT_LABEL, FONT_SMALL,
    PDF_FONT_LABELS, PDF_FONTS, TK_FONT_MAP,
    RIGHT_PANEL_W, PAD_S, PAD_M, PAD_L,
)
from src.gui.widgets.tooltip import Tooltip
from src.gui.panels.thumbnail import ThumbnailPanel
from src.gui.panels.toc_panel import TocPanel

if TYPE_CHECKING:
    from src.core.document import PDFDocument


def _rgb255_to_hex(rgb: tuple) -> str:
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"


def _mk_btn(parent, text, cmd, bg=None, fg=None, font=None,
            padx=PAD_M, pady=PAD_S, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg or PALETTE["bg_hover"],
        fg=fg or PALETTE["fg_primary"],
        activebackground=PALETTE["accent_dim"],
        activeforeground=PALETTE["accent_light"],
        font=font or FONT_LABEL,
        relief="flat", bd=0, padx=padx, pady=pady,
        cursor="hand2", highlightthickness=0, **kw,
    )


def _mk_label(parent, text, fg=None, font=None, **kw):
    return tk.Label(
        parent, text=text,
        bg=PALETTE["bg_panel"],
        fg=fg or PALETTE["fg_secondary"],
        font=font or FONT_LABEL, **kw,
    )


def _mk_entry(parent, var, width=18, **kw):
    return tk.Entry(
        parent, textvariable=var,
        bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
        insertbackground=PALETTE["fg_primary"],
        selectbackground=PALETTE["accent_dim"],
        relief="flat", highlightthickness=1,
        highlightbackground=PALETTE["border"],
        highlightcolor=PALETTE["accent"],
        font=FONT_UI, width=width, **kw,
    )


class RightPanel:
    """
    Right-hand inspector panel (tabbed).

    Parameters
    ----------
    parent : tk.Widget
        Body frame.
    get_doc : callable → PDFDocument | None
    get_current_page : callable → int
    thumbnail_callbacks : dict
        Forwarded to ``ThumbnailPanel``.
    toc_callbacks : dict
        Expected keys:
          ``on_navigate``      callable(page_idx: int)
          ``on_toc_changed``   callable(new_toc: list)
    tool_style_state : dict
        Mutable dict of current tool style values.
    on_tool_style_change : callable(key, value) | None
    """

    _STYLE_DEFAULTS: dict = {
        "annot_stroke_rgb":    (92, 138, 110),
        "annot_fill_rgb":      None,
        "annot_width":         1.5,
        "draw_mode":           "pen",
        "draw_stroke_rgb":     (92, 138, 110),
        "draw_fill_rgb":       None,
        "draw_width":          2.0,
        "draw_opacity":        1.0,
        "font_index":          0,
        "fontsize":            14,
        "text_color":          (0, 0, 0),
        "text_align":          0,
        "redact_fill_color":   (0.0, 0.0, 0.0),
        "redact_label":        "",
    }

    def __init__(
        self,
        parent: tk.Widget,
        get_doc,
        get_current_page,
        thumbnail_callbacks: dict,
        tool_style_state: dict,
        on_tool_style_change=None,
        toc_callbacks: dict | None = None,
    ) -> None:
        self._get_doc          = get_doc
        self._get_current_page = get_current_page
        self._thumb_cbs        = thumbnail_callbacks
        self._toc_cbs          = toc_callbacks or {}
        self._style            = tool_style_state
        self._on_style_change  = on_tool_style_change

        self._visible = True
        self._nb: ttk.Notebook | None = None
        self._tab_props: tk.Frame | None = None
        self._props_content_frame: tk.Frame | None = None
        self._page_label: tk.Label | None = None
        self.thumb: ThumbnailPanel | None = None
        self.toc_panel: TocPanel | None = None

        # Per-panel widget refs (populated lazily by props builders)
        self._sb_font_var:  tk.StringVar | None = None
        self._sb_size_var:  tk.IntVar    | None = None
        self._sb_align_btns: list        = []
        self._text_color_swatch: tk.Button | None = None

        self._annot_stroke_sw:    tk.Button   | None = None
        self._annot_fill_swatch:  tk.Button   | None = None
        self._annot_fill_none_var: tk.BooleanVar | None = None
        self._annot_width_var:    tk.DoubleVar | None = None

        self._draw_mode_btns:    dict        = {}
        self._draw_stroke_sw:    tk.Button   | None = None
        self._draw_fill_swatch:  tk.Button   | None = None
        self._draw_fill_none_var: tk.BooleanVar | None = None
        self._draw_width_var:    tk.DoubleVar | None = None
        self._draw_opacity_var:  tk.IntVar   | None = None

        self._redact_fill_sw:        tk.Button   | None = None
        self._redact_label_var:      tk.StringVar | None = None
        self._redact_query_var:      tk.StringVar | None = None
        self._redact_case_var:       tk.BooleanVar | None = None
        self._redact_confirm_frame:  tk.Frame     | None = None
        self._redact_hit_label:      tk.Label     | None = None

        self.frame = self._build(parent)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self, parent: tk.Widget) -> tk.Frame:
        panel = tk.Frame(
            parent, bg=PALETTE["bg_panel"],
            width=RIGHT_PANEL_W, highlightthickness=0,
        )
        panel.pack(side=tk.RIGHT, fill=tk.Y)
        panel.pack_propagate(False)

        # Header with hide button
        hdr = tk.Frame(panel, bg=PALETTE["bg_mid"], height=30)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="INSPECTOR",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            font=("Helvetica Neue", 8, "bold"),
        ).pack(side=tk.LEFT, padx=PAD_M, fill=tk.Y)
        tk.Button(
            hdr, text="×", command=self.toggle_visibility,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            activebackground=PALETTE["bg_hover"],
            font=("Helvetica Neue", 11), relief="flat", bd=0,
            padx=8, cursor="hand2", highlightthickness=0,
        ).pack(side=tk.RIGHT, fill=tk.Y)

        # Outer notebook: Pages | Properties
        nb = ttk.Notebook(panel, style="Right.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True)
        self._nb = nb

        tab_pages = tk.Frame(nb, bg=PALETTE["bg_panel"])
        nb.add(tab_pages, text=" Pages ")

        self._tab_props = tk.Frame(nb, bg=PALETTE["bg_panel"])
        nb.add(self._tab_props, text=" Properties ")

        self._build_pages_tab(tab_pages)
        self._build_props_placeholder(self._tab_props)

        return panel

    # ── Pages tab (inner notebook: Thumbnails | Bookmarks) ────────────────────

    def _build_pages_tab(self, parent: tk.Widget) -> None:
        # ── Navigation row ────────────────────────────────────────────────────
        nav = tk.Frame(parent, bg=PALETTE["bg_panel"])
        nav.pack(fill=tk.X, padx=PAD_M, pady=(PAD_M, PAD_S))

        _mk_btn(nav, "◀", self._thumb_cbs.get("prev_page", lambda: None),
                padx=PAD_S).pack(side=tk.LEFT)

        self._page_jump_var   = tk.StringVar(value="—")
        self._total_pages     = 0
        self._page_label_mode = "label"

        self._page_nav_frame = tk.Frame(nav, bg=PALETTE["bg_panel"])
        self._page_nav_frame.pack(side=tk.LEFT, expand=True)

        self._page_label = tk.Label(
            self._page_nav_frame, text="—",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"], font=FONT_UI,
            cursor="hand2",
        )
        self._page_label.pack()
        Tooltip(self._page_label, "Click to jump to a page")

        self._page_entry = tk.Entry(
            self._page_nav_frame,
            textvariable=self._page_jump_var,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            selectbackground=PALETTE["accent_dim"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["accent"],
            highlightcolor=PALETTE["accent"],
            font=FONT_UI, width=5, justify="center",
        )

        self._page_label.bind("<Button-1>", lambda e: self._enter_jump_mode())
        self._page_entry.bind("<Return>",   lambda e: self._commit_jump())
        self._page_entry.bind("<Escape>",   lambda e: self._exit_jump_mode())
        self._page_entry.bind("<FocusOut>", lambda e: self._exit_jump_mode())

        _mk_btn(nav, "▶", self._thumb_cbs.get("next_page", lambda: None),
                padx=PAD_S).pack(side=tk.RIGHT)

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(
            fill=tk.X, padx=PAD_M, pady=2)

        # ── Inner notebook: Thumbnails | Bookmarks ────────────────────────────
        inner_nb = ttk.Notebook(parent, style="Right.TNotebook")
        inner_nb.pack(fill=tk.BOTH, expand=True)

        thumb_tab = tk.Frame(inner_nb, bg=PALETTE["bg_panel"])
        inner_nb.add(thumb_tab, text=" Thumbnails ")

        toc_tab = tk.Frame(inner_nb, bg=PALETTE["bg_panel"])
        inner_nb.add(toc_tab, text=" Bookmarks ")

        # ── Thumbnail panel ───────────────────────────────────────────────────
        self.thumb = ThumbnailPanel(
            parent=thumb_tab,
            get_doc=self._get_doc,
            get_current_page=self._get_current_page,
            # FIX: removed the "on_" prefix from the dictionary keys
            on_page_click=self._thumb_cbs.get("page_click", lambda i: None),
            root=self._thumb_cbs["root"],
            on_reorder=self._thumb_cbs.get("reorder"),
            on_add_page=self._thumb_cbs.get("add_page"),
            on_delete_page=self._thumb_cbs.get("delete_page"),
            on_duplicate_page=self._thumb_cbs.get("duplicate_page"),
            on_rotate_page=self._thumb_cbs.get("rotate_page"),
            get_image_thumbnail=self._thumb_cbs.get("get_image_thumbnail"),
        )

        # ── TOC panel ─────────────────────────────────────────────────────────
        self.toc_panel = TocPanel(
            parent=toc_tab,
            on_navigate=self._toc_cbs.get("on_navigate", lambda i: None),
            on_toc_changed=self._toc_cbs.get("on_toc_changed", lambda t: None),
            get_page_count=self._toc_cbs.get("get_page_count", lambda: 0),
        )

    # ── Page label / jump ─────────────────────────────────────────────────────

    def update_page_label(self, current: int, total: int) -> None:
        self._total_pages = total
        if self._page_label:
            self._page_label.config(text=f"{current} / {total}")
        if self._page_label_mode == "entry":
            self._exit_jump_mode()

    def _enter_jump_mode(self) -> None:
        if not self._total_pages:
            return
        current_text = self._page_label.cget("text")
        try:
            current_num = current_text.split("/")[0].strip()
        except Exception:
            current_num = ""
        self._page_jump_var.set(current_num)
        self._page_label.pack_forget()
        self._page_entry.pack()
        self._page_entry.focus_set()
        self._page_entry.select_range(0, tk.END)
        self._page_label_mode = "entry"

    def _exit_jump_mode(self) -> None:
        self._page_entry.pack_forget()
        self._page_label.pack()
        self._page_label_mode = "label"

    def _commit_jump(self) -> None:
        raw = self._page_jump_var.get().strip()
        self._exit_jump_mode()
        on_jump = self._thumb_cbs.get("on_page_jump")
        if not on_jump or not raw:
            return
        try:
            page_num = int(raw)
        except ValueError:
            return
        on_jump(page_num)

    # ── TOC public helpers (called by main_window) ────────────────────────────

    def refresh_toc(self, toc: list[list]) -> None:
        """Repopulate the Bookmarks tab with *toc*."""
        if self.toc_panel:
            self.toc_panel.reset(toc)

    # ── Properties tab ────────────────────────────────────────────────────────

    def _build_props_placeholder(self, parent: tk.Widget) -> None:
        self._props_content_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        self._props_content_frame.pack(fill=tk.BOTH, expand=True)
        self._render_placeholder()

    def _render_placeholder(self) -> None:
        for w in self._props_content_frame.winfo_children():
            w.destroy()
        tk.Label(
            self._props_content_frame,
            text="Select a tool\nto see its options",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=FONT_LABEL, justify="center",
        ).place(relx=0.5, rely=0.4, anchor="center")

    def render_tool_props(self, tool_name: str) -> None:
        for w in self._props_content_frame.winfo_children():
            w.destroy()
        builders = {
            "text":         self._props_text,
            "highlight":    self._props_annot,
            "rect_annot":   self._props_annot,
            "draw":         self._props_draw,
            "redact":       self._props_redact,
            "select_text":  self._props_select,
            "insert_image": self._props_insert_image,
            "extract":      self._props_extract,
        }
        builder = builders.get(tool_name)
        if builder:
            builder(self._props_content_frame)
        else:
            self._render_placeholder()

    def select_properties_tab(self) -> None:
        if self._nb:
            self._nb.select(1)

    # ── visibility toggle ─────────────────────────────────────────────────────

    def toggle_visibility(self) -> None:
        if self._visible:
            self.frame.pack_forget()
            self._visible = False
        else:
            self.frame.pack(side=tk.RIGHT, fill=tk.Y)
            self._visible = True

    # ── section helpers ───────────────────────────────────────────────────────

    def _section(self, parent: tk.Widget, title: str) -> None:
        tk.Label(
            parent, text=title.upper(),
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=("Helvetica Neue", 8, "bold"), anchor="w",
        ).pack(fill=tk.X, padx=PAD_L, pady=(PAD_L, 2))
        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(
            fill=tk.X, padx=PAD_L, pady=(0, PAD_S))

    def _color_swatch(self, parent, get_hex, on_pick) -> tk.Button:
        btn = tk.Button(
            parent, text="  ", relief="flat", bd=0,
            bg=get_hex(), cursor="hand2", command=on_pick,
            highlightthickness=2, highlightbackground=PALETTE["border"], width=3,
        )
        return btn

    # ── Properties: Text ──────────────────────────────────────────────────────

    def _props_text(self, parent: tk.Widget) -> None:
        self._section(parent, "Font")
        row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(row, "Family").pack(side=tk.LEFT)
        self._sb_font_var = tk.StringVar(
            value=PDF_FONT_LABELS[self._style.get("font_index", 0)])
        fc = ttk.Combobox(row, textvariable=self._sb_font_var,
                          values=PDF_FONT_LABELS, state="readonly", width=14)
        fc.pack(side=tk.RIGHT)
        fc.bind("<<ComboboxSelected>>", lambda _: self._on_font_change())

        row2 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row2.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(row2, "Size (pt)").pack(side=tk.LEFT)
        self._sb_size_var = tk.IntVar(value=self._style.get("fontsize", 14))
        tk.Spinbox(
            row2, from_=6, to=144, textvariable=self._sb_size_var,
            width=5, command=self._on_size_change,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            buttonbackground=PALETTE["border"], relief="flat",
            highlightthickness=0,
        ).pack(side=tk.RIGHT)

        self._section(parent, "Colour & Alignment")
        color_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        color_row.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(color_row, "Color").pack(side=tk.LEFT)
        tc = self._style.get("text_color", (0, 0, 0))
        self._text_color_swatch = self._color_swatch(
            color_row, lambda: _rgb255_to_hex(self._style.get("text_color", (0, 0, 0))),
            self._pick_text_color,
        )
        self._text_color_swatch.configure(bg=_rgb255_to_hex(tc))
        self._text_color_swatch.pack(side=tk.RIGHT)

        align_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        align_row.pack(fill=tk.X, padx=PAD_L, pady=4)
        _mk_label(align_row, "Align").pack(side=tk.LEFT)
        aframe = tk.Frame(align_row, bg=PALETTE["bg_panel"])
        aframe.pack(side=tk.RIGHT)
        self._sb_align_btns = []
        for idx, (sym, tip) in enumerate([("≡L","Left"),("≡C","Center"),
                                          ("≡R","Right"),("≡J","Justify")]):
            b = tk.Button(
                aframe, text=sym, width=2,
                font=("Helvetica Neue", 8), relief="flat", bd=0,
                padx=2, pady=2, cursor="hand2",
                command=lambda i=idx: self._on_align_change(i),
                bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
                activebackground=PALETTE["accent_subtle"], highlightthickness=0,
            )
            b.pack(side=tk.LEFT, padx=1)
            Tooltip(b, tip)
            self._sb_align_btns.append(b)
        self._refresh_align()

    # ── Properties: Annotation ────────────────────────────────────────────────

    def _props_annot(self, parent: tk.Widget) -> None:
        self._section(parent, "Stroke")
        r1 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r1.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r1, "Color").pack(side=tk.LEFT)
        self._annot_stroke_sw = self._color_swatch(
            r1,
            lambda: _rgb255_to_hex(self._style.get("annot_stroke_rgb", (92,138,110))),
            self._pick_annot_stroke,
        )
        self._annot_stroke_sw.configure(
            bg=_rgb255_to_hex(self._style.get("annot_stroke_rgb", (92, 138, 110))))
        self._annot_stroke_sw.pack(side=tk.RIGHT)

        r2 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r2.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r2, "Width").pack(side=tk.LEFT)
        self._annot_width_var = tk.DoubleVar(value=self._style.get("annot_width", 1.5))
        sp = tk.Spinbox(
            r2, from_=0.5, to=10.0, increment=0.5,
            textvariable=self._annot_width_var, width=5,
            command=self._on_annot_width_change,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            buttonbackground=PALETTE["border"], relief="flat", highlightthickness=0,
        )
        sp.pack(side=tk.RIGHT)
        sp.bind("<Return>", lambda e: self._on_annot_width_change())

        self._section(parent, "Fill")
        fr = tk.Frame(parent, bg=PALETTE["bg_panel"])
        fr.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._annot_fill_none_var = tk.BooleanVar(
            value=(self._style.get("annot_fill_rgb") is None))
        tk.Checkbutton(
            fr, text="No fill", variable=self._annot_fill_none_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            selectcolor=PALETTE["accent_dim"], activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2",
            command=self._on_annot_fill_toggle, highlightthickness=0,
        ).pack(side=tk.LEFT)
        fill_rgb = self._style.get("annot_fill_rgb") or (255, 255, 0)
        self._annot_fill_swatch = tk.Button(
            fr, text="  ", relief="flat", bd=0, width=3,
            bg=_rgb255_to_hex(fill_rgb), cursor="hand2",
            command=self._pick_annot_fill,
            highlightthickness=2, highlightbackground=PALETTE["border"],
            state=tk.DISABLED if self._style.get("annot_fill_rgb") is None else tk.NORMAL,
        )
        self._annot_fill_swatch.pack(side=tk.RIGHT)

    # ── Properties: Draw ──────────────────────────────────────────────────────

    def _props_draw(self, parent: tk.Widget) -> None:
        self._section(parent, "Mode")
        mode_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        mode_frame.pack(fill=tk.X, padx=PAD_L, pady=(0, PAD_S))
        self._draw_mode_btns = {}
        for mode, label in [("pen","✏ Pen"),("line","╱ Line"),
                             ("arrow","→ Arrow"),("ellipse","○ Ellipse")]:
            b = tk.Button(
                mode_frame, text=label,
                font=("Helvetica Neue", 8), relief="flat", bd=0,
                padx=4, pady=3, cursor="hand2",
                command=lambda m=mode: self._on_draw_mode(m),
                highlightthickness=0,
            )
            b.pack(side=tk.LEFT, padx=1)
            self._draw_mode_btns[mode] = b
        self._refresh_draw_mode_btns()

        self._section(parent, "Stroke")
        r1 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r1.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r1, "Color").pack(side=tk.LEFT)
        self._draw_stroke_sw = self._color_swatch(
            r1,
            lambda: _rgb255_to_hex(self._style.get("draw_stroke_rgb", (92,138,110))),
            self._pick_draw_stroke,
        )
        self._draw_stroke_sw.configure(
            bg=_rgb255_to_hex(self._style.get("draw_stroke_rgb", (92, 138, 110))))
        self._draw_stroke_sw.pack(side=tk.RIGHT)

        r2 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r2.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r2, "Width").pack(side=tk.LEFT)
        self._draw_width_var = tk.DoubleVar(value=self._style.get("draw_width", 2.0))
        sp = tk.Spinbox(
            r2, from_=0.5, to=20.0, increment=0.5,
            textvariable=self._draw_width_var, width=5,
            command=self._on_draw_width_change,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            buttonbackground=PALETTE["border"], relief="flat", highlightthickness=0,
        )
        sp.pack(side=tk.RIGHT)
        sp.bind("<Return>", lambda e: self._on_draw_width_change())

        self._section(parent, "Fill")
        fr = tk.Frame(parent, bg=PALETTE["bg_panel"])
        fr.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._draw_fill_none_var = tk.BooleanVar(
            value=(self._style.get("draw_fill_rgb") is None))
        tk.Checkbutton(
            fr, text="No fill", variable=self._draw_fill_none_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            selectcolor=PALETTE["accent_dim"], activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2",
            command=self._on_draw_fill_toggle, highlightthickness=0,
        ).pack(side=tk.LEFT)
        draw_fill = self._style.get("draw_fill_rgb") or (255, 255, 136)
        self._draw_fill_swatch = tk.Button(
            fr, text="  ", relief="flat", bd=0, width=3,
            bg=_rgb255_to_hex(draw_fill), cursor="hand2",
            command=self._pick_draw_fill,
            highlightthickness=2, highlightbackground=PALETTE["border"],
            state=tk.DISABLED if self._style.get("draw_fill_rgb") is None else tk.NORMAL,
        )
        self._draw_fill_swatch.pack(side=tk.RIGHT)

        self._section(parent, "Opacity")
        self._draw_opacity_var = tk.IntVar(
            value=int(self._style.get("draw_opacity", 1.0) * 100))
        tk.Scale(
            parent, from_=10, to=100, variable=self._draw_opacity_var,
            orient=tk.HORIZONTAL, showvalue=True,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            troughcolor=PALETTE["bg_hover"],
            highlightthickness=0, bd=0,
            command=lambda v: self._on_draw_opacity_change(),
        ).pack(fill=tk.X, padx=PAD_L, pady=(0, PAD_S))
        tk.Label(
            parent, text="Shift+drag: snap to 45°",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"], font=FONT_SMALL,
        ).pack(anchor="w", padx=PAD_L)

    # ── Properties: Redact ───────────────────────────────────────────────────

    def _props_redact(self, parent: tk.Widget) -> None:
        self._section(parent, "Fill")
        r = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r, "Color").pack(side=tk.LEFT)

        def _rfill_hex():
            rv, gv, bv = [int(v * 255) for v in self._style.get("redact_fill_color",
                                                                   (0.0, 0.0, 0.0))]
            return f"#{rv:02x}{gv:02x}{bv:02x}"

        self._redact_fill_sw = tk.Button(
            r, text="  ", relief="flat", bd=0, width=3,
            bg=_rfill_hex(), cursor="hand2", command=self._pick_redact_fill,
            highlightthickness=2, highlightbackground=PALETTE["border"],
        )
        self._redact_fill_sw.pack(side=tk.RIGHT)

        self._section(parent, "Label")
        lf = tk.Frame(parent, bg=PALETTE["bg_panel"])
        lf.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._redact_label_var = tk.StringVar(
            value=self._style.get("redact_label", ""))
        e = _mk_entry(lf, self._redact_label_var, width=16)
        e.pack(fill=tk.X)
        e.bind("<KeyRelease>", lambda ev: self._on_redact_label_change())
        tk.Label(
            lf, text='e.g. "[REDACTED]" or blank',
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"], font=FONT_SMALL,
        ).pack(anchor="w", pady=(2, 0))

        self._section(parent, "Search & Redact")
        sf = tk.Frame(parent, bg=PALETTE["bg_panel"])
        sf.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._redact_query_var = tk.StringVar()
        qe = _mk_entry(sf, self._redact_query_var, width=16)
        qe.pack(fill=tk.X, pady=(0, 4))
        qe.bind("<Return>", lambda ev: self._cb_redact_find())

        self._redact_case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            sf, text="Case-sensitive", variable=self._redact_case_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            selectcolor=PALETTE["accent_dim"], activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2", highlightthickness=0,
        ).pack(anchor="w", pady=(0, 6))

        _mk_btn(sf, "🔍 Find on Page", self._cb_redact_find,
                bg=PALETTE["accent"], fg=PALETTE["fg_inverse"],
                font=FONT_LABEL).pack(fill=tk.X, pady=(0, 4))

        self._redact_confirm_frame = tk.Frame(sf, bg=PALETTE["bg_panel"])
        self._redact_confirm_frame.pack(fill=tk.X, pady=(0, 4))
        self._redact_confirm_frame.pack_forget()

        self._redact_hit_label = tk.Label(
            self._redact_confirm_frame, text="",
            bg=PALETTE["bg_panel"], fg=PALETTE["danger"],
            font=("Helvetica Neue", 8, "bold"),
        )
        self._redact_hit_label.pack(anchor="w", pady=(0, 4))

        _mk_btn(self._redact_confirm_frame, "⬛ Redact All",
                self._cb_redact_confirm,
                bg=PALETTE["danger"], fg="#0F0F13",
                font=("Helvetica Neue", 9, "bold")).pack(fill=tk.X, pady=(0, 2))
        _mk_btn(self._redact_confirm_frame, "✕ Cancel",
                self._cb_redact_cancel,
                bg=PALETTE["bg_hover"], fg=PALETTE["fg_secondary"]).pack(fill=tk.X)

    # ── Properties: simple info panels ───────────────────────────────────────

    def _props_select(self, parent: tk.Widget) -> None:
        self._section(parent, "Select Text")
        tk.Label(
            parent,
            text="Click a text block\nor drag to select multiple.\n\nCtrl+C copies selection.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, justify="left",
        ).pack(padx=PAD_L, anchor="w")

    def _props_insert_image(self, parent: tk.Widget) -> None:
        self._section(parent, "Insert Image")
        tk.Label(
            parent,
            text="1. Click canvas to\n   choose an image file.\n2. Drag to place it.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, justify="left",
        ).pack(padx=PAD_L, anchor="w")

    def _props_extract(self, parent: tk.Widget) -> None:
        self._section(parent, "Extract Image")
        tk.Label(
            parent,
            text="Click directly on an\nimage to extract\nand save it.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, justify="left",
        ).pack(padx=PAD_L, anchor="w")

    # ── widget change callbacks ───────────────────────────────────────────────

    def _notify(self, key: str, value) -> None:
        self._style[key] = value
        if self._on_style_change:
            self._on_style_change(key, value)

    def _on_font_change(self) -> None:
        idx = PDF_FONT_LABELS.index(self._sb_font_var.get())
        self._notify("font_index", idx)

    def _on_size_change(self) -> None:
        try:
            self._notify("fontsize", max(6, min(144, int(self._sb_size_var.get()))))
        except (ValueError, tk.TclError):
            pass

    def _on_align_change(self, align: int) -> None:
        self._notify("text_align", align)
        self._refresh_align()

    def _refresh_align(self) -> None:
        current = self._style.get("text_align", 0)
        for i, btn in enumerate(self._sb_align_btns):
            if i == current:
                btn.config(bg=PALETTE["accent"], fg=PALETTE["fg_inverse"])
            else:
                btn.config(bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"])

    def _pick_text_color(self) -> None:
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self._style.get("text_color", (0, 0, 0))),
            title="Text Color")
        if result and result[0]:
            rgb = tuple(int(v) for v in result[0])
            self._notify("text_color", rgb)
            if self._text_color_swatch:
                self._text_color_swatch.config(bg=_rgb255_to_hex(rgb))

    def _pick_annot_stroke(self) -> None:
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self._style.get("annot_stroke_rgb", (92,138,110))),
            title="Annotation Stroke Color")
        if result and result[0]:
            rgb = tuple(int(v) for v in result[0])
            self._notify("annot_stroke_rgb", rgb)
            if self._annot_stroke_sw:
                self._annot_stroke_sw.config(bg=_rgb255_to_hex(rgb))

    def _on_annot_fill_toggle(self) -> None:
        if self._annot_fill_none_var and self._annot_fill_none_var.get():
            self._notify("annot_fill_rgb", None)
            if self._annot_fill_swatch:
                self._annot_fill_swatch.config(state=tk.DISABLED)
        else:
            if self._style.get("annot_fill_rgb") is None:
                self._notify("annot_fill_rgb", (255, 255, 0))
            if self._annot_fill_swatch:
                self._annot_fill_swatch.config(
                    bg=_rgb255_to_hex(self._style["annot_fill_rgb"]),
                    state=tk.NORMAL)

    def _pick_annot_fill(self) -> None:
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self._style.get("annot_fill_rgb") or (255, 255, 0)),
            title="Annotation Fill Color")
        if result and result[0]:
            rgb = tuple(int(v) for v in result[0])
            self._notify("annot_fill_rgb", rgb)
            if self._annot_fill_swatch:
                self._annot_fill_swatch.config(bg=_rgb255_to_hex(rgb))

    def _on_annot_width_change(self) -> None:
        try:
            val = max(0.5, min(10.0, float(self._annot_width_var.get())))
            self._notify("annot_width", val)
        except (ValueError, tk.TclError):
            pass

    def _on_draw_mode(self, mode: str) -> None:
        self._notify("draw_mode", mode)
        self._refresh_draw_mode_btns()

    def _refresh_draw_mode_btns(self) -> None:
        current = self._style.get("draw_mode", "pen")
        for m, btn in self._draw_mode_btns.items():
            if m == current:
                btn.config(bg=PALETTE["accent"], fg=PALETTE["fg_inverse"])
            else:
                btn.config(bg=PALETTE["bg_hover"], fg=PALETTE["fg_secondary"])

    def _pick_draw_stroke(self) -> None:
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self._style.get("draw_stroke_rgb", (92,138,110))),
            title="Draw Stroke Color")
        if result and result[0]:
            rgb = tuple(int(v) for v in result[0])
            self._notify("draw_stroke_rgb", rgb)
            if self._draw_stroke_sw:
                self._draw_stroke_sw.config(bg=_rgb255_to_hex(rgb))

    def _on_draw_fill_toggle(self) -> None:
        if self._draw_fill_none_var and self._draw_fill_none_var.get():
            self._notify("draw_fill_rgb", None)
            if self._draw_fill_swatch:
                self._draw_fill_swatch.config(state=tk.DISABLED)
        else:
            if self._style.get("draw_fill_rgb") is None:
                self._notify("draw_fill_rgb", (255, 255, 136))
            if self._draw_fill_swatch:
                self._draw_fill_swatch.config(
                    bg=_rgb255_to_hex(self._style["draw_fill_rgb"]),
                    state=tk.NORMAL)

    def _pick_draw_fill(self) -> None:
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self._style.get("draw_fill_rgb") or (255, 255, 136)),
            title="Draw Fill Color")
        if result and result[0]:
            rgb = tuple(int(v) for v in result[0])
            self._notify("draw_fill_rgb", rgb)
            if self._draw_fill_swatch:
                self._draw_fill_swatch.config(bg=_rgb255_to_hex(rgb))

    def _on_draw_width_change(self) -> None:
        try:
            val = max(0.5, float(self._draw_width_var.get()))
            self._notify("draw_width", val)
        except (ValueError, tk.TclError):
            pass

    def _on_draw_opacity_change(self) -> None:
        try:
            val = max(0.1, min(1.0, self._draw_opacity_var.get() / 100))
            self._notify("draw_opacity", val)
        except (ValueError, tk.TclError):
            pass

    def _pick_redact_fill(self) -> None:
        r, g, b = [int(v * 255) for v in self._style.get(
            "redact_fill_color", (0.0, 0.0, 0.0))]
        result = colorchooser.askcolor(
            color=f"#{r:02x}{g:02x}{b:02x}", title="Redaction Fill Color")
        if result and result[0]:
            r8, g8, b8 = [int(v) for v in result[0]]
            fill = (r8 / 255, g8 / 255, b8 / 255)
            self._notify("redact_fill_color", fill)
            if self._redact_fill_sw:
                self._redact_fill_sw.config(bg=f"#{r8:02x}{g8:02x}{b8:02x}")

    def _on_redact_label_change(self) -> None:
        self._notify("redact_label", self._redact_label_var.get())

    def _cb_redact_find(self) -> None:
        if self._on_style_change:
            self._on_style_change("redact.find", {
                "query": self._redact_query_var.get().strip() if self._redact_query_var else "",
                "case_sensitive": self._redact_case_var.get() if self._redact_case_var else False,
            })

    def _cb_redact_confirm(self) -> None:
        if self._on_style_change:
            self._on_style_change("redact.confirm", None)
        if self._redact_confirm_frame:
            self._redact_confirm_frame.pack_forget()

    def _cb_redact_cancel(self) -> None:
        if self._on_style_change:
            self._on_style_change("redact.cancel", None)
        if self._redact_confirm_frame:
            self._redact_confirm_frame.pack_forget()

    def show_redact_confirm(self, hit_count: int) -> None:
        if self._redact_hit_label:
            self._redact_hit_label.config(
                text=f"⚠ {hit_count} match(es) across all pages")
        if self._redact_confirm_frame:
            self._redact_confirm_frame.pack(fill=tk.X, pady=(0, 4))

    def hide_redact_confirm(self) -> None:
        if self._redact_confirm_frame:
            self._redact_confirm_frame.pack_forget()