"""
PDF Editor — Main Window  (UI Overhaul)

Layout
──────
  ┌─────────────────────────────────────────────────────────┐
  │  TOP BAR  [Logo | File actions | Title | Zoom | View]   │
  ├──┬──────────────────────────────────────────┬───────────┤
  │  │                                          │  Pages /  │
  │ I│          C A N V A S                    │  Props    │
  │ C│                                          │  (tabbed) │
  │ O│                                          │           │
  │ N│                                          │           │
  │  │                                          │           │
  ├──┴──────────────────────────────────────────┴───────────┤
  │  STATUS BAR                                             │
  └─────────────────────────────────────────────────────────┘

Left strip  — thin icon-only toolbar (52 px).
Right panel — tabbed: "Pages" (thumbnails) + "Properties" (context-aware).
Canvas      — maximum real-estate; no hard borders.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from src.core.document import PDFDocument
from src.services.page_service       import PageService
from src.services.image_service      import ImageService
from src.services.text_service       import TextService
from src.services.annotation_service import AnnotationService
from src.services.redaction_service  import RedactionService

from src.commands.insert_text  import InsertTextBoxCommand
from src.commands.rotate_page  import RotatePageCommand
from src.commands.page_ops     import ReorderPagesCommand, DuplicatePageCommand
from src.commands.draw_command import DrawAnnotationCommand

from src.gui.theme import (
    PALETTE, FONT_MONO, FONT_UI, FONT_UI_MED, FONT_LABEL, FONT_SMALL, FONT_TITLE,
    PDF_FONTS, PDF_FONT_LABELS, TK_FONT_MAP,
    RENDER_DPI, MIN_SCALE, MAX_SCALE, SCALE_STEP,
    ICON_BAR_W, RIGHT_PANEL_W, TAB_BAR_H,
    THUMB_SCALE, THUMB_PAD, THUMB_PANEL_W,
    PAD_S, PAD_M, PAD_L, PAD_XL,
)
from src.gui.history_manager         import HistoryManager
from src.gui.widgets.tooltip         import Tooltip
from src.gui.widgets.text_box        import TextBox
from src.gui.panels.thumbnail        import ThumbnailPanel
from src.gui.tools.annot_tool        import AnnotationTool
from src.gui.tools.image_tool        import ImageInsertTool, ImageExtractTool
from src.gui.tools.select_tool       import SelectTextTool
from src.gui.tools.redact_tool       import RedactTool
from src.gui.tools.draw_tool         import DrawTool
from src.utils.recent_files          import RecentFiles
from src.services.image_conversion   import ImageConversionService
from src.commands.convert_images     import ConvertImagesToPdfCommand
from src.commands.ocr_page           import OcrPageCommand

try:
    from src.services.merge_split_service   import MergeSplitService
    from src.gui.panels.merge_split_dialog  import MergeSplitDialog
    _HAS_MERGE_SPLIT = True
except ImportError:
    _HAS_MERGE_SPLIT = False


# ══════════════════════════════════════════════════════════════════════════════
#  AppContext
# ══════════════════════════════════════════════════════════════════════════════

class AppContext:
    def __init__(self, editor: "InteractivePDFEditor"):
        self._editor = editor
        self.on_tool_state_change = None

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

    def canvas_to_pdf(self, cx, cy):
        return self._editor._canvas_to_pdf(cx, cy)

    def push_history(self, cmd):
        self._editor._push_history(cmd)

    def render(self):
        self._editor._render()

    def flash_status(self, message, color=None, duration_ms=3000):
        self._editor._flash_status(message, color, duration_ms)

    def navigate_to_page(self, idx):
        self._editor._navigate_to(idx)

    def set_tool_state(self, key, value):
        if self.on_tool_state_change:
            self.on_tool_state_change(key, value)


# ══════════════════════════════════════════════════════════════════════════════
#  Helpers — styled widget factories
# ══════════════════════════════════════════════════════════════════════════════

def _mk_btn(parent, text, cmd, bg=None, fg=None, font=None, padx=PAD_M, pady=PAD_S, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=bg or PALETTE["bg_hover"],
        fg=fg or PALETTE["fg_primary"],
        activebackground=PALETTE["accent_dim"],
        activeforeground=PALETTE["accent_light"],
        font=font or FONT_LABEL,
        relief="flat", bd=0,
        padx=padx, pady=pady,
        cursor="hand2",
        highlightthickness=0,
        **kw,
    )


def _mk_label(parent, text, fg=None, font=None, **kw):
    return tk.Label(
        parent, text=text,
        bg=PALETTE["bg_panel"],
        fg=fg or PALETTE["fg_secondary"],
        font=font or FONT_LABEL,
        **kw,
    )


def _mk_sep(parent, orient="h", bg=None):
    bg = bg or PALETTE["border"]
    if orient == "h":
        return tk.Frame(parent, bg=bg, height=1)
    return tk.Frame(parent, bg=bg, width=1)


def _mk_entry(parent, var, width=18, **kw):
    return tk.Entry(
        parent, textvariable=var,
        bg=PALETTE["bg_hover"],
        fg=PALETTE["fg_primary"],
        insertbackground=PALETTE["fg_primary"],
        selectbackground=PALETTE["accent_dim"],
        relief="flat",
        highlightthickness=1,
        highlightbackground=PALETTE["border"],
        highlightcolor=PALETTE["accent"],
        font=FONT_UI,
        width=width,
        **kw,
    )


def _rgb255_to_hex(rgb):
    r, g, b = [max(0, min(255, int(v))) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"


# ══════════════════════════════════════════════════════════════════════════════
#  InteractivePDFEditor
# ══════════════════════════════════════════════════════════════════════════════

class InteractivePDFEditor:

    # ── Tools definition — (internal_name, icon, tooltip, group) ─────────────
    _TOOLS = [
        # group separator label, then tools
        ("__sep__", None, "Selection", None),
        ("select_text",  "⬚",  "Select Text  — click or drag to copy text",         "select"),
        ("__sep__", None, "Markup", None),
        ("highlight",    "▐",  "Highlight  — drag to mark a region",                "markup"),
        ("rect_annot",   "▭",  "Rectangle  — drag to draw a box annotation",        "markup"),
        ("draw",         "✏",  "Draw  — freehand pen, lines, arrows, shapes",       "markup"),
        ("redact",       "⬛",  "Redact  — permanently remove content",              "markup"),
        ("__sep__", None, "Insert / Extract", None),
        ("text",         "T",  "Add Text  — click to place a text box",             "insert"),
        ("insert_image", "⊞",  "Insert Image  — choose then drag to place",         "insert"),
        ("extract",      "⇥",  "Extract Image  — click an image to save it",        "insert"),
    ]

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF Editor")
        self.root.geometry("1280x860")
        self.root.minsize(900, 640)
        self.root.configure(bg=PALETTE["bg_dark"])

        # Services
        self.page_service        = PageService()
        self.text_service        = TextService()
        self.image_service       = ImageService()
        self.annotation_service  = AnnotationService()
        self.redaction_service   = RedactionService()
        self.image_conversion_service = ImageConversionService()
        if _HAS_MERGE_SPLIT:
            self.merge_split_service = MergeSplitService()

        # Document state
        self.doc: PDFDocument | None = None
        self.current_page_idx  = 0
        self.scale_factor      = RENDER_DPI
        self.tk_image          = None
        self._page_offset_x    = PAD_XL
        self._page_offset_y    = PAD_XL
        self._continuous_mode  = True
        self._cont_images: dict  = {}
        self._cont_after_id     = None
        self._scroll_after_id   = None
        self._current_path: str | None = None
        self._unsaved_changes   = False

        # Staging (images → PDF)
        self._is_staging_mode   = False
        self._staging_images: list[str] = []
        self._staging_ocr_var   = tk.BooleanVar(value=False)

        # Tool style state
        self.active_tool         = tk.StringVar(value="text")
        self.annot_stroke_rgb    = (92, 138, 110)    # sage green default
        self.annot_fill_rgb: tuple | None = None
        self.annot_width         = 1.5
        self.draw_mode           = "pen"
        self.draw_stroke_rgb     = (92, 138, 110)
        self.draw_fill_rgb: tuple | None = None
        self.draw_width          = 2.0
        self.draw_opacity        = 1.0
        self.redact_fill_color   = (0.0, 0.0, 0.0)
        self.redact_label        = ""
        self.font_index          = 0
        self.fontsize            = 14
        self.text_color          = (0, 0, 0)
        self.text_align          = 0

        # Text boxes
        self._text_boxes: list[TextBox] = []
        self._suppress_next_click = False

        # History
        self._history = HistoryManager(on_change=self._on_history_change)

        # Recent files
        self._recent = RecentFiles()

        # Search bar state
        self._search_bar_visible = False
        self._search_bar_frame   = None

        # Build UI
        self._build_ui()
        self._apply_ttk_style()

        # AppContext + tools
        self._ctx = AppContext(self)
        self._ctx.on_tool_state_change = self._on_tool_state_change
        self._tools: dict = {}
        self._current_tool = None
        self._init_tools()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.after(50, self._rebuild_recent_menu)
        self.root.after(60, self._show_startup_screen)

    # ── TTK global style ──────────────────────────────────────────────────────

    def _apply_ttk_style(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass

        # Comboboxes
        s.configure("TCombobox",
                    fieldbackground=PALETTE["bg_hover"],
                    background=PALETTE["bg_hover"],
                    foreground=PALETTE["fg_primary"],
                    selectbackground=PALETTE["accent_dim"],
                    selectforeground=PALETTE["fg_primary"],
                    bordercolor=PALETTE["border"],
                    lightcolor=PALETTE["border"],
                    darkcolor=PALETTE["border"],
                    arrowcolor=PALETTE["fg_secondary"],
                    insertcolor=PALETTE["fg_primary"])
        s.map("TCombobox",
              fieldbackground=[("readonly", PALETTE["bg_hover"])],
              selectbackground=[("readonly", PALETTE["accent_dim"])])

        # Scrollbars — slim and tonal
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar",
                        background=PALETTE["bg_panel"],
                        troughcolor=PALETTE["bg_dark"],
                        bordercolor=PALETTE["bg_panel"],
                        arrowcolor=PALETTE["fg_dim"],
                        gripcount=0,
                        relief="flat")
            s.map(f"{orient}.TScrollbar",
                  background=[("active", PALETTE["bg_hover"])])

        # Notebook tabs (right panel)
        s.configure("Right.TNotebook",
                    background=PALETTE["bg_panel"],
                    borderwidth=0,
                    tabmargins=[0, 0, 0, 0])
        s.configure("Right.TNotebook.Tab",
                    background=PALETTE["bg_panel"],
                    foreground=PALETTE["fg_dim"],
                    padding=[PAD_M, PAD_S],
                    font=FONT_LABEL,
                    borderwidth=0)
        s.map("Right.TNotebook.Tab",
              background=[("selected", PALETTE["bg_card"])],
              foreground=[("selected", PALETTE["fg_primary"])])

    # ── Tool init ─────────────────────────────────────────────────────────────

    def _init_tools(self):
        ctx = self._ctx
        self._tools["highlight"]    = AnnotationTool(
            ctx, self.annotation_service, "highlight",
            get_stroke_rgb=lambda: self.annot_stroke_rgb,
            get_fill_rgb=lambda:   self.annot_fill_rgb,
            get_width=lambda:      self.annot_width,
        )
        self._tools["rect_annot"]   = AnnotationTool(
            ctx, self.annotation_service, "rect_annot",
            get_stroke_rgb=lambda: self.annot_stroke_rgb,
            get_fill_rgb=lambda:   self.annot_fill_rgb,
            get_width=lambda:      self.annot_width,
        )
        self._tools["insert_image"] = ImageInsertTool(
            ctx, self.image_service,
            set_hint=lambda t: None,   # hint handled by status bar now
        )
        self._tools["extract"]      = ImageExtractTool(ctx, self.image_service)
        self._tools["select_text"]  = SelectTextTool(ctx, self.root)
        self._tools["redact"]       = RedactTool(
            ctx, self.redaction_service,
            get_fill_color=lambda:        self.redact_fill_color,
            get_replacement_text=lambda:  self.redact_label,
            on_navigate_page=self._navigate_to,
            on_hit_changed=self._on_search_hit_changed,
        )
        self._tools["draw"]         = DrawTool(
            ctx,
            get_mode=lambda:       self.draw_mode,
            get_stroke_rgb=lambda: self.draw_stroke_rgb,
            get_fill_rgb=lambda:   self.draw_fill_rgb,
            get_width=lambda:      self.draw_width,
            get_opacity=lambda:    self.draw_opacity,
            on_committed=self._on_draw_committed,
        )

    def _get_tool(self, name):
        return self._tools.get(name)

    # ══════════════════════════════════════════════════════════════════════════
    #  UI BUILD
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        self._build_topbar()

        # Body row: icon strip | canvas area | right panel
        self._body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        self._body.pack(fill=tk.BOTH, expand=True)

        self._build_icon_toolbar(self._body)
        self._build_right_panel(self._body)
        self._build_canvas_area(self._body)   # middle — packed last, expands

        self._build_statusbar()
        self._startup_frame = None

    # ── Top bar ───────────────────────────────────────────────────────────────

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["bg_mid"], height=48)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        # ── Left cluster: logo + file actions ────────────────────────────────
        left = tk.Frame(bar, bg=PALETTE["bg_mid"])
        left.pack(side=tk.LEFT, fill=tk.Y, padx=(PAD_M, 0))

        tk.Label(left, text="◼",
                 bg=PALETTE["bg_mid"], fg=PALETTE["accent"],
                 font=("Helvetica Neue", 14, "bold")).pack(side=tk.LEFT, padx=(0, PAD_S))

        for label, cmd, tip in [
            ("Open",    self._open_pdf,    "Open PDF  (Ctrl+O)"),
            ("Save",    self._save_pdf,    "Save  (Ctrl+S)"),
            ("Save As", self._save_pdf_as, "Save As  (Ctrl+Shift+S)"),
        ]:
            Tooltip(self._topbar_btn(left, label, cmd), tip)

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

        _mk_sep(left, "v").pack(side=tk.LEFT, fill=tk.Y, pady=10, padx=PAD_S)

        Tooltip(self._topbar_btn(left, "↩ Undo", self._undo), "Undo  (Ctrl+Z)")
        Tooltip(self._topbar_btn(left, "↪ Redo", self._redo), "Redo  (Ctrl+Y)")

        # ── Centre: document title ────────────────────────────────────────────
        self._title_lbl = tk.Label(
            bar, text="PDF Editor",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            font=FONT_TITLE,
        )
        self._title_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # ── Right cluster: zoom + view + secondary actions ────────────────────
        right = tk.Frame(bar, bg=PALETTE["bg_mid"])
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, PAD_M))

        # Secondary actions
        if _HAS_MERGE_SPLIT:
            Tooltip(
                self._topbar_btn(right, "Merge / Split", self._open_merge_split_dialog),
                "Merge or split PDF files",
            )
        Tooltip(
            self._topbar_btn(right, "Images → PDF", self._start_image_staging),
            "Combine images into a PDF",
        )
        Tooltip(
            self._topbar_btn(right, "🔍 Find", self._toggle_search_bar),
            "Find & Redact text  (Ctrl+F)",
        )

        _mk_sep(right, "v").pack(side=tk.LEFT, fill=tk.Y, pady=10, padx=PAD_S)

        # Zoom
        tk.Label(right, text="Zoom", bg=PALETTE["bg_mid"],
                 fg=PALETTE["fg_dim"], font=FONT_SMALL).pack(side=tk.LEFT, padx=(PAD_S, 2))
        Tooltip(self._topbar_btn(right, "−", self._zoom_out, padx=6), "Zoom out  (Ctrl+−)")
        self._zoom_label = tk.Label(right, text="100%",
                                    bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
                                    font=FONT_MONO, width=5)
        self._zoom_label.pack(side=tk.LEFT)
        Tooltip(self._topbar_btn(right, "+", self._zoom_in, padx=6), "Zoom in  (Ctrl+=)")
        Tooltip(self._topbar_btn(right, "⟳", self._zoom_reset, padx=6), "Reset zoom  (Ctrl+0)")

        _mk_sep(right, "v").pack(side=tk.LEFT, fill=tk.Y, pady=10, padx=PAD_S)

        # View toggle
        self._btn_single = self._topbar_btn(right, "□ Page", self._set_single_mode)
        self._btn_scroll = self._topbar_btn(right, "▤ Scroll", self._set_continuous_mode)
        Tooltip(self._btn_single, "Single page view")
        Tooltip(self._btn_scroll, "Continuous scroll view")
        self._update_view_mode_buttons()

        # Key bindings
        self.root.bind("<Control-o>",     lambda e: self._open_pdf())
        self.root.bind("<Control-s>",     lambda e: self._save_pdf())
        self.root.bind("<Control-S>",     lambda e: self._save_pdf_as())
        self.root.bind("<Control-z>",     lambda e: self._undo())
        self.root.bind("<Control-y>",     lambda e: self._redo())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>",     lambda e: self._zoom_reset())
        self.root.bind("<Left>",          lambda e: self._prev_page())
        self.root.bind("<Right>",         lambda e: self._next_page())
        self.root.bind("<Escape>",        lambda e: self._on_escape())
        self.root.bind("<Control-c>",     lambda e: self._copy_selected_text())
        self.root.bind("<Control-f>",     lambda e: self._toggle_search_bar())
        self.root.bind("<F3>",            lambda e: self._search_bar_next())
        self.root.bind("<Shift-F3>",      lambda e: self._search_bar_prev())
        self.root.bind("<Control-t>",     lambda e: self._toggle_right_panel())

        self._update_zoom_label()

    def _topbar_btn(self, parent, text, cmd, padx=PAD_M, **kw):
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
        for key, val in kw.items():
            btn.configure(**{key: val})
        return btn

    # ── Left icon toolbar ─────────────────────────────────────────────────────

    def _build_icon_toolbar(self, parent):
        self._icon_bar = tk.Frame(
            parent, bg=PALETTE["bg_panel"],
            width=ICON_BAR_W,
            highlightthickness=0,
        )
        self._icon_bar.pack(side=tk.LEFT, fill=tk.Y)
        self._icon_bar.pack_propagate(False)

        # Top spacer
        tk.Frame(self._icon_bar, bg=PALETTE["bg_panel"], height=PAD_M).pack()

        self._icon_btns: dict = {}

        for entry in self._TOOLS:
            name, icon, tip, group = entry

            if name == "__sep__":
                # Section label
                tk.Frame(self._icon_bar, bg=PALETTE["border"], height=1).pack(
                    fill=tk.X, padx=8, pady=(PAD_M, 2))
                tk.Label(self._icon_bar, text=icon,   # icon is actually the label text here
                         bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                         font=("Helvetica Neue", 7), anchor="center").pack(fill=tk.X)
                continue

            btn = tk.Button(
                self._icon_bar,
                text=icon,
                command=lambda n=name: self._select_tool(n),
                bg=PALETTE["bg_panel"],
                fg=PALETTE["fg_secondary"],
                activebackground=PALETTE["accent_subtle"],
                activeforeground=PALETTE["accent_light"],
                font=("Helvetica Neue", 14),
                relief="flat", bd=0,
                width=2, pady=PAD_S,
                cursor="hand2",
                highlightthickness=0,
            )
            btn.pack(fill=tk.X, padx=4, pady=1)
            self._icon_btns[name] = btn
            Tooltip(btn, tip)

        # Page action buttons at the bottom
        tk.Frame(self._icon_bar, bg=PALETTE["bg_panel"]).pack(fill=tk.BOTH, expand=True)
        _mk_sep(self._icon_bar).pack(fill=tk.X, padx=8, pady=(PAD_S, 2))

        for icon, cmd, tip in [
            ("↺", lambda: self._rotate(-90), "Rotate Left"),
            ("↻", lambda: self._rotate(90),  "Rotate Right"),
            ("+", self._add_page,             "Add Page"),
            ("✕", self._delete_page,          "Delete Page"),
            ("👁", self._ocr_current_page,     "OCR Page"),
        ]:
            b = tk.Button(
                self._icon_bar, text=icon,
                command=cmd,
                bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                activebackground=PALETTE["bg_hover"],
                activeforeground=PALETTE["fg_primary"],
                font=("Helvetica Neue", 11),
                relief="flat", bd=0,
                width=2, pady=4,
                cursor="hand2", highlightthickness=0,
            )
            b.pack(fill=tk.X, padx=4, pady=1)
            Tooltip(b, tip)

        tk.Frame(self._icon_bar, bg=PALETTE["bg_panel"], height=PAD_M).pack()

        # Initial active state
        self._refresh_icon_states()

    def _select_tool(self, name: str):
        self.active_tool.set(name)
        self._on_tool_change()

    def _refresh_icon_states(self):
        active = self.active_tool.get()
        for name, btn in self._icon_btns.items():
            if name == active:
                btn.configure(
                    bg=PALETTE["accent_subtle"],
                    fg=PALETTE["accent_light"],
                )
            else:
                btn.configure(
                    bg=PALETTE["bg_panel"],
                    fg=PALETTE["fg_secondary"],
                )

    # ── Right panel (tabbed) ──────────────────────────────────────────────────

    def _build_right_panel(self, parent):
        self._right_panel = tk.Frame(
            parent, bg=PALETTE["bg_panel"],
            width=RIGHT_PANEL_W,
            highlightthickness=0,
        )
        self._right_panel.pack(side=tk.RIGHT, fill=tk.Y)
        self._right_panel.pack_propagate(False)
        self._right_panel_visible = True

        # Header with toggle button
        hdr = tk.Frame(self._right_panel, bg=PALETTE["bg_mid"], height=30)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(hdr, text="INSPECTOR",
                 bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
                 font=("Helvetica Neue", 8, "bold")).pack(side=tk.LEFT, padx=PAD_M, fill=tk.Y)

        hide_btn = tk.Button(hdr, text="×",
                             bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
                             activebackground=PALETTE["bg_hover"],
                             font=("Helvetica Neue", 11), relief="flat", bd=0,
                             padx=8, cursor="hand2", command=self._toggle_right_panel,
                             highlightthickness=0)
        hide_btn.pack(side=tk.RIGHT, fill=tk.Y)

        # Notebook
        nb = ttk.Notebook(self._right_panel, style="Right.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True)
        self._right_nb = nb

        # Tab 1 — Pages
        self._tab_pages = tk.Frame(nb, bg=PALETTE["bg_panel"])
        nb.add(self._tab_pages, text=" Pages ")

        # Tab 2 — Properties
        self._tab_props = tk.Frame(nb, bg=PALETTE["bg_panel"])
        nb.add(self._tab_props, text=" Properties ")

        self._build_pages_tab(self._tab_pages)
        self._build_props_tab_placeholder(self._tab_props)

    def _toggle_right_panel(self):
        if self._right_panel_visible:
            self._right_panel.pack_forget()
            self._right_panel_visible = False
        else:
            # Re-pack before canvas
            self._right_panel.pack(side=tk.RIGHT, fill=tk.Y, before=self.canvas)
            self._right_panel_visible = True

    # ── Pages tab ─────────────────────────────────────────────────────────────

    def _build_pages_tab(self, parent):
        # Nav row
        nav = tk.Frame(parent, bg=PALETTE["bg_panel"])
        nav.pack(fill=tk.X, padx=PAD_M, pady=(PAD_M, PAD_S))

        _mk_btn(nav, "◀", self._prev_page, padx=PAD_S).pack(side=tk.LEFT)
        self._page_label = tk.Label(
            nav, text="—",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            font=FONT_UI,
        )
        self._page_label.pack(side=tk.LEFT, expand=True)
        _mk_btn(nav, "▶", self._next_page, padx=PAD_S).pack(side=tk.RIGHT)

        _mk_sep(parent).pack(fill=tk.X, padx=PAD_M, pady=2)

        # Thumbnail panel fills the rest
        self._thumb = ThumbnailPanel(
            parent=parent,
            get_doc=lambda: self.doc,
            get_current_page=lambda: self.current_page_idx,
            on_page_click=self._thumb_page_click,
            root=self.root,
            on_reorder=self._thumb_reorder,
            on_add_page=self._thumb_add_page,
            on_delete_page=self._thumb_delete_page,
            on_duplicate_page=self._thumb_duplicate_page,
            on_rotate_page=self._thumb_rotate_page,
            get_image_thumbnail=self._get_image_thumbnail,
        )

    # ── Properties tab ────────────────────────────────────────────────────────

    def _build_props_tab_placeholder(self, parent):
        """Initial state — shown when no document is open or no tool selected."""
        self._props_content_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        self._props_content_frame.pack(fill=tk.BOTH, expand=True)
        self._render_props_placeholder()

    def _render_props_placeholder(self):
        for w in self._props_content_frame.winfo_children():
            w.destroy()
        tk.Label(
            self._props_content_frame,
            text="Select a tool\nto see its options",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=FONT_LABEL, justify="center",
        ).place(relx=0.5, rely=0.4, anchor="center")

    def _render_tool_props(self, tool_name: str):
        """Swap the Properties tab content for the active tool."""
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
            self._render_props_placeholder()

    # ── Properties panels ─────────────────────────────────────────────────────

    def _props_section(self, parent, title):
        tk.Label(parent, text=title.upper(),
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                 font=("Helvetica Neue", 8, "bold"),
                 anchor="w").pack(fill=tk.X, padx=PAD_L, pady=(PAD_L, 2))
        _mk_sep(parent).pack(fill=tk.X, padx=PAD_L, pady=(0, PAD_S))

    def _props_row(self, parent, label, widget_factory):
        row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(row, label).pack(side=tk.LEFT)
        w = widget_factory(row)
        if w:
            w.pack(side=tk.RIGHT)
        return row

    def _color_swatch(self, parent, get_hex, on_pick):
        btn = tk.Button(
            parent, text="  ", relief="flat", bd=0,
            bg=get_hex(), cursor="hand2",
            command=on_pick,
            highlightthickness=2,
            highlightbackground=PALETTE["border"],
            width=3,
        )
        return btn

    def _props_text(self, parent):
        self._props_section(parent, "Font")
        row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(row, "Family").pack(side=tk.LEFT)
        self._sb_font_var = tk.StringVar(value=PDF_FONT_LABELS[self.font_index])
        fc = ttk.Combobox(row, textvariable=self._sb_font_var,
                          values=PDF_FONT_LABELS, state="readonly", width=14)
        fc.pack(side=tk.RIGHT)
        fc.bind("<<ComboboxSelected>>", lambda _: self._sb_font_change())

        row2 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        row2.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(row2, "Size (pt)").pack(side=tk.LEFT)
        self._sb_size_var = tk.IntVar(value=self.fontsize)
        tk.Spinbox(row2, from_=6, to=144, textvariable=self._sb_size_var, width=5,
                   command=self._sb_size_change,
                   bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                   buttonbackground=PALETTE["border"],
                   relief="flat", highlightthickness=0).pack(side=tk.RIGHT)

        self._props_section(parent, "Colour & Alignment")
        color_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        color_row.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(color_row, "Color").pack(side=tk.LEFT)
        self._text_color_swatch = self._color_swatch(
            color_row,
            lambda: _rgb255_to_hex(self.text_color),
            self._pick_global_color,
        )
        self._text_color_swatch.configure(bg=_rgb255_to_hex(self.text_color))
        self._text_color_swatch.pack(side=tk.RIGHT)

        align_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        align_row.pack(fill=tk.X, padx=PAD_L, pady=4)
        _mk_label(align_row, "Align").pack(side=tk.LEFT)
        aframe = tk.Frame(align_row, bg=PALETTE["bg_panel"])
        aframe.pack(side=tk.RIGHT)
        self._sb_align_btns = []
        for idx, (sym, tip) in enumerate([("≡L","Left"),("≡C","Center"),("≡R","Right"),("≡J","Justify")]):
            b = tk.Button(aframe, text=sym, width=2,
                          font=("Helvetica Neue", 8), relief="flat", bd=0,
                          padx=2, pady=2, cursor="hand2",
                          command=lambda i=idx: self._sb_align_change(i),
                          bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
                          activebackground=PALETTE["accent_subtle"],
                          highlightthickness=0)
            b.pack(side=tk.LEFT, padx=1)
            Tooltip(b, tip)
            self._sb_align_btns.append(b)
        self._sb_refresh_align()

    def _props_annot(self, parent):
        self._props_section(parent, "Stroke")
        r1 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r1.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r1, "Color").pack(side=tk.LEFT)
        self._annot_stroke_sw = self._color_swatch(
            r1, lambda: _rgb255_to_hex(self.annot_stroke_rgb),
            self._pick_annot_stroke_color)
        self._annot_stroke_sw.configure(bg=_rgb255_to_hex(self.annot_stroke_rgb))
        self._annot_stroke_sw.pack(side=tk.RIGHT)

        r2 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r2.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r2, "Width").pack(side=tk.LEFT)
        self._annot_width_var = tk.DoubleVar(value=self.annot_width)
        sp = tk.Spinbox(r2, from_=0.5, to=10.0, increment=0.5,
                        textvariable=self._annot_width_var, width=5,
                        command=self._on_annot_width_change,
                        bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                        buttonbackground=PALETTE["border"],
                        relief="flat", highlightthickness=0)
        sp.pack(side=tk.RIGHT)
        sp.bind("<Return>", lambda e: self._on_annot_width_change())

        self._props_section(parent, "Fill")
        fr = tk.Frame(parent, bg=PALETTE["bg_panel"])
        fr.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._annot_fill_none_var = tk.BooleanVar(value=(self.annot_fill_rgb is None))
        tk.Checkbutton(fr, text="No fill",
                       variable=self._annot_fill_none_var,
                       bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                       selectcolor=PALETTE["accent_dim"],
                       activebackground=PALETTE["bg_hover"],
                       font=FONT_LABEL, cursor="hand2",
                       command=self._on_annot_fill_toggle,
                       highlightthickness=0).pack(side=tk.LEFT)
        self._annot_fill_swatch = tk.Button(
            fr, text="  ", relief="flat", bd=0, width=3,
            bg=_rgb255_to_hex(self.annot_fill_rgb or (255, 255, 0)),
            cursor="hand2", command=self._pick_annot_fill_color,
            highlightthickness=2, highlightbackground=PALETTE["border"],
            state=tk.DISABLED if self.annot_fill_rgb is None else tk.NORMAL)
        self._annot_fill_swatch.pack(side=tk.RIGHT)

    def _props_draw(self, parent):
        self._props_section(parent, "Mode")
        mode_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        mode_frame.pack(fill=tk.X, padx=PAD_L, pady=(0, PAD_S))
        self._draw_mode_btns: dict = {}
        for mode, label in [("pen","✏ Pen"),("line","╱ Line"),("arrow","→ Arrow"),("ellipse","○ Ellipse")]:
            b = tk.Button(mode_frame, text=label,
                          font=("Helvetica Neue", 8), relief="flat", bd=0,
                          padx=4, pady=3, cursor="hand2",
                          command=lambda m=mode: self._set_draw_mode(m),
                          highlightthickness=0)
            b.pack(side=tk.LEFT, padx=1)
            self._draw_mode_btns[mode] = b
        self._refresh_draw_mode_btns()

        self._props_section(parent, "Stroke")
        r1 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r1.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r1, "Color").pack(side=tk.LEFT)
        self._draw_stroke_sw = self._color_swatch(
            r1, lambda: _rgb255_to_hex(self.draw_stroke_rgb),
            self._pick_draw_stroke_color)
        self._draw_stroke_sw.configure(bg=_rgb255_to_hex(self.draw_stroke_rgb))
        self._draw_stroke_sw.pack(side=tk.RIGHT)

        r2 = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r2.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r2, "Width").pack(side=tk.LEFT)
        self._draw_width_var = tk.DoubleVar(value=self.draw_width)
        sp = tk.Spinbox(r2, from_=0.5, to=20.0, increment=0.5,
                        textvariable=self._draw_width_var, width=5,
                        command=self._on_draw_width_change,
                        bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                        buttonbackground=PALETTE["border"],
                        relief="flat", highlightthickness=0)
        sp.pack(side=tk.RIGHT)
        sp.bind("<Return>", lambda e: self._on_draw_width_change())

        self._props_section(parent, "Fill")
        fr = tk.Frame(parent, bg=PALETTE["bg_panel"])
        fr.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._draw_fill_none_var = tk.BooleanVar(value=(self.draw_fill_rgb is None))
        tk.Checkbutton(fr, text="No fill",
                       variable=self._draw_fill_none_var,
                       bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                       selectcolor=PALETTE["accent_dim"],
                       activebackground=PALETTE["bg_hover"],
                       font=FONT_LABEL, cursor="hand2",
                       command=self._on_draw_fill_toggle,
                       highlightthickness=0).pack(side=tk.LEFT)
        self._draw_fill_swatch = tk.Button(
            fr, text="  ", relief="flat", bd=0, width=3,
            bg=_rgb255_to_hex(self.draw_fill_rgb or (255, 255, 136)),
            cursor="hand2", command=self._pick_draw_fill_color,
            highlightthickness=2, highlightbackground=PALETTE["border"],
            state=tk.DISABLED if self.draw_fill_rgb is None else tk.NORMAL)
        self._draw_fill_swatch.pack(side=tk.RIGHT)

        self._props_section(parent, "Opacity")
        self._draw_opacity_var = tk.IntVar(value=int(self.draw_opacity * 100))
        tk.Scale(parent, from_=10, to=100, variable=self._draw_opacity_var,
                 orient=tk.HORIZONTAL, showvalue=True,
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                 troughcolor=PALETTE["bg_hover"],
                 highlightthickness=0, bd=0,
                 command=lambda v: self._on_draw_opacity_change(),
                 ).pack(fill=tk.X, padx=PAD_L, pady=(0, PAD_S))

        tk.Label(parent, text="Shift+drag: snap to 45°",
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                 font=FONT_SMALL).pack(anchor="w", padx=PAD_L)

    def _props_redact(self, parent):
        self._props_section(parent, "Fill")
        r = tk.Frame(parent, bg=PALETTE["bg_panel"])
        r.pack(fill=tk.X, padx=PAD_L, pady=2)
        _mk_label(r, "Color").pack(side=tk.LEFT)
        def _rfill_hex():
            rv, gv, bv = [int(v*255) for v in self.redact_fill_color]
            return f"#{rv:02x}{gv:02x}{bv:02x}"
        self._redact_fill_sw = tk.Button(
            r, text="  ", relief="flat", bd=0, width=3,
            bg=_rfill_hex(), cursor="hand2",
            command=self._pick_redact_fill_color,
            highlightthickness=2, highlightbackground=PALETTE["border"])
        self._redact_fill_sw.pack(side=tk.RIGHT)

        self._props_section(parent, "Label")
        lf = tk.Frame(parent, bg=PALETTE["bg_panel"])
        lf.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._redact_label_var = tk.StringVar(value=self.redact_label)
        e = _mk_entry(lf, self._redact_label_var, width=16)
        e.pack(fill=tk.X)
        e.bind("<KeyRelease>", lambda ev: self._on_redact_label_change())
        tk.Label(lf, text='e.g. "[REDACTED]" or blank',
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                 font=FONT_SMALL).pack(anchor="w", pady=(2,0))

        self._props_section(parent, "Search & Redact")
        sf = tk.Frame(parent, bg=PALETTE["bg_panel"])
        sf.pack(fill=tk.X, padx=PAD_L, pady=2)
        self._redact_query_var = tk.StringVar()
        qe = _mk_entry(sf, self._redact_query_var, width=16)
        qe.pack(fill=tk.X, pady=(0,4))
        qe.bind("<Return>", lambda ev: self._redact_find())

        self._redact_case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(sf, text="Case-sensitive",
                       variable=self._redact_case_var,
                       bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                       selectcolor=PALETTE["accent_dim"],
                       activebackground=PALETTE["bg_hover"],
                       font=FONT_LABEL, cursor="hand2",
                       highlightthickness=0).pack(anchor="w", pady=(0,6))

        _mk_btn(sf, "🔍 Find on Page", self._redact_find,
                bg=PALETTE["accent"], fg=PALETTE["fg_inverse"],
                font=FONT_LABEL).pack(fill=tk.X, pady=(0,4))

        # Confirm frame
        self._redact_confirm_frame = tk.Frame(sf, bg=PALETTE["bg_panel"])
        self._redact_confirm_frame.pack(fill=tk.X, pady=(0,4))
        self._redact_confirm_frame.pack_forget()

        self._redact_hit_label = tk.Label(
            self._redact_confirm_frame, text="",
            bg=PALETTE["bg_panel"], fg=PALETTE["danger"],
            font=("Helvetica Neue", 8, "bold"))
        self._redact_hit_label.pack(anchor="w", pady=(0,4))

        _mk_btn(self._redact_confirm_frame, "⬛ Redact All", self._redact_confirm,
                bg=PALETTE["danger"], fg="#0F0F13",
                font=("Helvetica Neue", 9, "bold")).pack(fill=tk.X, pady=(0,2))
        _mk_btn(self._redact_confirm_frame, "✕ Cancel", self._redact_cancel_hits,
                bg=PALETTE["bg_hover"], fg=PALETTE["fg_secondary"]).pack(fill=tk.X)

    def _props_select(self, parent):
        self._props_section(parent, "Select Text")
        tk.Label(parent,
                 text="Click a text block\nor drag to select multiple.\n\nCtrl+C copies selection.",
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
                 font=FONT_LABEL, justify="left").pack(padx=PAD_L, anchor="w")

    def _props_insert_image(self, parent):
        self._props_section(parent, "Insert Image")
        tk.Label(parent,
                 text="1. Click canvas to\n   choose an image file.\n"
                      "2. Drag to place it.",
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
                 font=FONT_LABEL, justify="left").pack(padx=PAD_L, anchor="w")

    def _props_extract(self, parent):
        self._props_section(parent, "Extract Image")
        tk.Label(parent,
                 text="Click directly on an\nimage to extract\nand save it.",
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"],
                 font=FONT_LABEL, justify="left").pack(padx=PAD_L, anchor="w")

    # ── Canvas area (with inline search bar) ──────────────────────────────────

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=PALETTE["bg_dark"])
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inline search/redact bar
        self._search_bar_frame = tk.Frame(
            frame, bg=PALETTE["bg_mid"], height=44,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        # Hidden until Ctrl+F

        def _sb_btn(p, text, cmd, **kw):
            defaults = dict(
                bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                activebackground=PALETTE["accent_dim"],
                font=FONT_LABEL, relief="flat", bd=0,
                padx=8, pady=4, cursor="hand2", highlightthickness=0,
            )
            defaults.update(kw)
            return tk.Button(p, text=text, command=cmd, **defaults)

        _sb_btn(self._search_bar_frame, "✕", self._toggle_search_bar,
                bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"], font=("Helvetica Neue",11),
                padx=10).pack(side=tk.RIGHT)

        _mk_sep(self._search_bar_frame, "v").pack(side=tk.RIGHT, fill=tk.Y, pady=8)

        self._sb_redact_all_btn = tk.Button(
            self._search_bar_frame, text="⬛ Redact All",
            command=self._search_bar_redact_all,
            bg=PALETTE["danger"], fg="#0F0F13",
            activebackground="#A05050",
            font=("Helvetica Neue", 9, "bold"), relief="flat", bd=0,
            padx=10, pady=4, cursor="hand2", state=tk.DISABLED, highlightthickness=0)
        self._sb_redact_all_btn.pack(side=tk.RIGHT, padx=(0,4))

        self._sb_redact_one_btn = tk.Button(
            self._search_bar_frame, text="Redact This",
            command=self._search_bar_redact_one,
            bg="#7B2020", fg="#FFCCCC",
            activebackground="#9B3030",
            font=FONT_LABEL, relief="flat", bd=0,
            padx=8, pady=4, cursor="hand2", state=tk.DISABLED, highlightthickness=0)
        self._sb_redact_one_btn.pack(side=tk.RIGHT, padx=(0,4))

        _mk_sep(self._search_bar_frame, "v").pack(side=tk.RIGHT, fill=tk.Y, pady=8)

        self._sb_hit_lbl = tk.Label(
            self._search_bar_frame, text="",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            font=FONT_MONO, padx=8, width=18, anchor="w")
        self._sb_hit_lbl.pack(side=tk.RIGHT)

        self._sb_next_btn = _sb_btn(self._search_bar_frame, "▶", self._search_bar_next, state=tk.DISABLED)
        self._sb_next_btn.pack(side=tk.RIGHT, padx=(0,2))
        self._sb_prev_btn = _sb_btn(self._search_bar_frame, "◀", self._search_bar_prev, state=tk.DISABLED)
        self._sb_prev_btn.pack(side=tk.RIGHT, padx=(0,2))

        _mk_sep(self._search_bar_frame, "v").pack(side=tk.RIGHT, fill=tk.Y, pady=8)

        tk.Label(self._search_bar_frame, text="🔍 Find & Redact:",
                 bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
                 font=FONT_LABEL, padx=8).pack(side=tk.LEFT)

        self._sb_query_var = tk.StringVar()
        self._sb_entry = tk.Entry(
            self._search_bar_frame, textvariable=self._sb_query_var,
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["border"],
            highlightcolor=PALETTE["accent"],
            width=28, font=FONT_UI)
        self._sb_entry.pack(side=tk.LEFT, padx=(0,6), ipady=4)
        self._sb_entry.bind("<Return>", lambda e: self._search_bar_find())
        self._sb_entry.bind("<Escape>", lambda e: self._toggle_search_bar())

        self._sb_case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self._search_bar_frame, text="Aa", variable=self._sb_case_var,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            selectcolor=PALETTE["accent_dim"],
            activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2", highlightthickness=0,
        ).pack(side=tk.LEFT, padx=(0,6))

        _sb_btn(self._search_bar_frame, "Search All Pages", self._search_bar_find,
                ).pack(side=tk.LEFT, padx=(0,4))

        # Scrollbars + canvas
        self.v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(
            frame, bg=PALETTE["canvas_bg"],
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
            highlightthickness=0,
            cursor="crosshair",
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        self.canvas.bind("<Button-1>",          self._on_canvas_click)
        self.canvas.bind("<B1-Motion>",          self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>",    self._on_canvas_release)
        self.canvas.bind("<MouseWheel>",         self._on_mousewheel)
        self.canvas.bind("<Button-4>",           self._on_mousewheel)
        self.canvas.bind("<Button-5>",           self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>", self._on_ctrl_scroll)
        self.canvas.bind("<Control-Button-4>",   self._on_ctrl_scroll)
        self.canvas.bind("<Control-Button-5>",   self._on_ctrl_scroll)
        self.canvas.bind("<Motion>",             self._on_mouse_motion)
        self.canvas.bind("<Configure>",          lambda e: self._render())

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["shadow"], height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        def sep():
            tk.Frame(bar, bg=PALETTE["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=4)

        self._st_tool = tk.Label(bar, text="Tool: Text",
                                 bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
                                 font=FONT_MONO, padx=10)
        self._st_tool.pack(side=tk.LEFT)
        sep()
        self._st_coords = tk.Label(bar, text="x: —    y: —",
                                   bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
                                   font=FONT_MONO, padx=10)
        self._st_coords.pack(side=tk.LEFT)
        sep()
        self._st_size = tk.Label(bar, text="",
                                 bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
                                 font=FONT_MONO, padx=10)
        self._st_size.pack(side=tk.LEFT)
        sep()
        self._st_action = tk.Label(bar, text="",
                                   bg=PALETTE["shadow"], fg=PALETTE["success"],
                                   font=FONT_MONO, padx=10)
        self._st_action.pack(side=tk.LEFT)
        self._st_zoom = tk.Label(bar, text="",
                                 bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
                                 font=FONT_MONO, padx=10)
        self._st_zoom.pack(side=tk.RIGHT)

    # ══════════════════════════════════════════════════════════════════════════
    #  Tool change
    # ══════════════════════════════════════════════════════════════════════════

    def _on_tool_change(self):
        tool_name = self.active_tool.get()
        self._st_tool.config(text=f"Tool: {tool_name.replace('_',' ').title()}")

        if self._current_tool is not None:
            self._current_tool.deactivate()

        if tool_name != "redact":
            rt = self._get_tool("redact")
            if rt and rt.has_pending_hits:
                rt.cancel_hits()

        cursor_map = {
            "text": "crosshair", "insert_image": "crosshair",
            "highlight": "crosshair", "rect_annot": "crosshair",
            "select_text": "ibeam", "extract": "arrow",
            "redact": "crosshair", "draw": "crosshair",
        }
        self.canvas.config(cursor=cursor_map.get(tool_name, "crosshair"))

        self._refresh_icon_states()
        self._render_tool_props(tool_name)

        # Auto-switch to Properties tab
        self._right_nb.select(1)

        self._current_tool = self._get_tool(tool_name)
        if self._current_tool:
            self._current_tool.activate()

    def _on_tool_state_change(self, key: str, value):
        """Route tool-state events (currently used by RedactTool)."""
        if key == "redact.hits_found":
            pass  # handled via on_hit_changed callback

    # ══════════════════════════════════════════════════════════════════════════
    #  Startup / welcome screen
    # ══════════════════════════════════════════════════════════════════════════

    def _show_startup_screen(self):
        if self.doc:
            return
        self._hide_startup_screen()

        frame = tk.Frame(self.canvas, bg=PALETTE["bg_dark"])
        self._startup_frame = frame

        inner = tk.Frame(frame, bg=PALETTE["bg_dark"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(inner, text="◼",
                 bg=PALETTE["bg_dark"], fg=PALETTE["accent"],
                 font=("Helvetica Neue", 52)).pack(pady=(0, 4))
        tk.Label(inner, text="PDF Editor",
                 bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"],
                 font=("Helvetica Neue", 22, "bold")).pack()
        tk.Label(inner, text="Open a PDF file to get started",
                 bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"],
                 font=("Helvetica Neue", 10)).pack(pady=(4, 20))

        tk.Button(inner, text="  Open PDF…  ",
                  command=self._open_pdf,
                  bg=PALETTE["accent"], fg=PALETTE["fg_inverse"],
                  activebackground=PALETTE["accent_light"],
                  activeforeground=PALETTE["fg_inverse"],
                  font=("Helvetica Neue", 12, "bold"),
                  relief="flat", bd=0, padx=28, pady=10,
                  cursor="hand2", highlightthickness=0).pack(pady=(0, 28))

        recents = self._recent.get()
        if recents:
            _mk_sep(inner).pack(fill=tk.X, pady=(0, 12))
            tk.Label(inner, text="RECENT FILES",
                     bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"],
                     font=("Helvetica Neue", 8, "bold")).pack(anchor="w", pady=(0, 6))

            for p in recents:
                row = tk.Frame(inner, bg=PALETTE["bg_dark"], cursor="hand2")
                row.pack(fill=tk.X, pady=1)
                name = os.path.basename(p)
                directory = os.path.dirname(p)
                if len(directory) > 48:
                    directory = "…" + directory[-46:]
                nl = tk.Label(row, text=name, bg=PALETTE["bg_dark"],
                              fg=PALETTE["fg_primary"], font=("Helvetica Neue", 10),
                              anchor="w", cursor="hand2")
                nl.pack(anchor="w")
                pl = tk.Label(row, text=directory, bg=PALETTE["bg_dark"],
                              fg=PALETTE["fg_dim"], font=("Helvetica Neue", 8),
                              anchor="w", cursor="hand2")
                pl.pack(anchor="w")

                def _enter(e, r=row, n=nl, pp=pl):
                    r.config(bg=PALETTE["bg_hover"])
                    n.config(bg=PALETTE["bg_hover"], fg=PALETTE["accent_light"])
                    pp.config(bg=PALETTE["bg_hover"])
                def _leave(e, r=row, n=nl, pp=pl):
                    r.config(bg=PALETTE["bg_dark"])
                    n.config(bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"])
                    pp.config(bg=PALETTE["bg_dark"])
                def _click(e, fp=p):
                    self._open_pdf_path(fp)

                for w in (row, nl, pl):
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)
                    w.bind("<Button-1>", _click)

                _mk_sep(inner).pack(fill=tk.X, pady=(4, 0))

        frame.place(x=0, y=0, relwidth=1, relheight=1)

    def _hide_startup_screen(self):
        if hasattr(self, "_startup_frame") and self._startup_frame:
            try:
                self._startup_frame.destroy()
            except Exception:
                pass
            self._startup_frame = None

    # ══════════════════════════════════════════════════════════════════════════
    #  All methods below are functionally identical to the original
    #  main_window.py — only styling constants are updated.
    # ══════════════════════════════════════════════════════════════════════════

    # ── Recent files ──────────────────────────────────────────────────────────

    def _rebuild_recent_menu(self):
        menu = tk.Menu(
            self._recent_mb, tearoff=0,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            activebackground=PALETTE["accent_dim"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica Neue", 9),
            relief="flat", bd=1,
        )
        recents = self._recent.get()
        if recents:
            for p in recents:
                label = os.path.basename(p)
                dirname = os.path.dirname(p)
                if len(dirname) > 40:
                    dirname = "…" + dirname[-38:]
                menu.add_command(
                    label=f"  {label}\n  {dirname}",
                    command=lambda fp=p: self._open_recent(fp),
                )
            menu.add_separator()
            menu.add_command(label="  Clear recent files",
                             command=self._clear_recent,
                             foreground=PALETTE["fg_dim"])
        else:
            menu.add_command(label="  No recent files", state="disabled")
        self._recent_mb.config(menu=menu)

    def _clear_recent(self):
        self._recent.clear()
        self._rebuild_recent_menu()
        if hasattr(self, "_startup_frame") and self._startup_frame:
            self._show_startup_screen()

    # ── File operations ───────────────────────────────────────────────────────

    def _open_pdf(self):
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes",
                                            "You have unsaved changes.\nSave before opening?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        path = filedialog.askopenfilename(
            title="Open PDF", filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")])
        if path:
            self._open_pdf_path(path)

    def _open_pdf_path(self, path: str):
        self._is_staging_mode = False
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
        try:
            self.doc = PDFDocument(path)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open:\n{ex}")
            self._recent.remove(path)
            self._rebuild_recent_menu()
            return
        self.current_page_idx = 0
        self._current_path    = path
        self._unsaved_changes = False
        self._history.clear()
        self._cont_images.clear()
        self._recent.add(path)
        self._rebuild_recent_menu()
        self._hide_startup_screen()
        self._update_title()
        self._render()
        self._thumb.reset()

    def _open_recent(self, path: str):
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes",
                                            "You have unsaved changes.\nSave before opening?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        self._open_pdf_path(path)

    def _save_pdf(self) -> bool:
        if self._is_staging_mode:
            return self._generate_pdf_from_staging()
        if not self.doc:
            return False
        if not self._current_path:
            return self._save_pdf_as()
        self._commit_all_boxes()
        try:
            self.doc.save(self._current_path, incremental=True)
            self._unsaved_changes = False
            self._update_title()
            self._flash_status("✓ Saved")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    def _save_pdf_as(self) -> bool:
        if not self.doc:
            return False
        self._commit_all_boxes()
        path = filedialog.asksaveasfilename(
            title="Save PDF As", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=os.path.basename(self._current_path) if self._current_path else "document.pdf",
        )
        if not path:
            self._flash_status("Save cancelled", color=PALETTE["fg_secondary"])
            return False
        try:
            self.doc.save(path)
            self._current_path    = path
            self._unsaved_changes = False
            self.doc.path         = path
            self._update_title()
            self._flash_status(f"✓ Saved as {os.path.basename(path)}")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    # ── Staging mode ──────────────────────────────────────────────────────────

    def _get_image_thumbnail(self, path: str, width: int) -> bytes:
        return self.image_conversion_service.get_image_thumbnail(path, width)

    def _start_image_staging(self):
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes",
                                            "Save before continuing?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        paths = filedialog.askopenfilenames(
            title="Select Images to Combine into PDF",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if not paths:
            return
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
            self.doc = None
        self._staging_images = list(paths)
        self._is_staging_mode = True
        self._current_path = None
        self._update_title()
        self._thumb.reset_for_images(self._staging_images)
        self._flash_status("Staging: drag thumbnails to reorder, then Save.")
        self._preview_staging_image(0)

    def _preview_staging_image(self, idx: int):
        if not self._is_staging_mode or idx >= len(self._staging_images):
            return
        self.current_page_idx = idx
        path = self._staging_images[idx]
        canvas_w = self.canvas.winfo_width()
        preview_w = int(canvas_w * 0.8 * self.scale_factor)
        img_bytes = self._get_image_thumbnail(path, width=preview_w)
        if img_bytes:
            self.tk_image = tk.PhotoImage(data=img_bytes)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_w // 2, 40, anchor=tk.N,
                                     image=self.tk_image, tags="page_img")
            self._page_label.config(text=f"{idx+1} / {len(self._staging_images)}")
            self._st_size.config(text="Image Preview")
            cb = tk.Checkbutton(
                self.canvas, text="Run OCR (make text selectable)",
                variable=self._staging_ocr_var,
                bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"],
                selectcolor=PALETTE["accent_dim"],
                activebackground=PALETTE["bg_hover"],
                highlightthickness=0)
            self.canvas.create_window(canvas_w // 2, 15, window=cb, tags="page_img")
            self._thumb.refresh_all_borders()
            self._thumb.scroll_to_active()

    def _exit_staging_mode(self):
        if not self._is_staging_mode:
            return
        self._is_staging_mode = False
        self._staging_images.clear()
        self.canvas.delete("all")
        self._thumb.reset()
        self._show_startup_screen()
        self._flash_status("Cancelled", color=PALETTE["fg_secondary"])

    def _generate_pdf_from_staging(self) -> bool:
        if not self._staging_images:
            return False
        out_path = filedialog.asksaveasfilename(
            title="Save Generated PDF", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")], initialfile="Combined_Images.pdf")
        if not out_path:
            return False
        self.root.config(cursor="watch")
        self.root.update()
        cmd = ConvertImagesToPdfCommand(
            self.image_conversion_service, self._staging_images, out_path,
            apply_ocr=self._staging_ocr_var.get())
        try:
            cmd.execute()
            if cmd.success:
                self._flash_status("✓ PDF created")
                self._is_staging_mode = False
                self._staging_images.clear()
                self._staging_ocr_var.set(False)
                self._open_pdf_path(out_path)
                return True
            messagebox.showerror("Error", "Failed to create PDF from images.")
            return False
        finally:
            self.root.config(cursor="")

    # ── OCR ───────────────────────────────────────────────────────────────────

    def _ocr_current_page(self):
        if not self.doc:
            return
        self.root.config(cursor="watch")
        self.root.update()
        cmd = OcrPageCommand(self.doc, self.current_page_idx)
        try:
            cmd.execute()
            self._push_history(cmd)
            self._flash_status("✓ OCR complete — text is now selectable.")
            sel = self._get_tool("select_text")
            if sel and self.active_tool.get() == "select_text":
                sel.reload()
            self._render()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("OCR Error", str(ex))
        finally:
            self.root.config(cursor="")

    # ── Merge / Split ─────────────────────────────────────────────────────────

    def _open_merge_split_dialog(self):
        if not _HAS_MERGE_SPLIT:
            return
        MergeSplitDialog(
            root=self.root,
            service=self.merge_split_service,
            current_doc=self.doc,
            on_open_path=self._open_pdf_path,
        )

    # ── Page management ───────────────────────────────────────────────────────

    def _prev_page(self):
        if self.doc and self.current_page_idx > 0:
            self._navigate_to(self.current_page_idx - 1)

    def _next_page(self):
        if self.doc and self.current_page_idx < self.doc.page_count - 1:
            self._navigate_to(self.current_page_idx + 1)

    def _navigate_to(self, idx: int):
        self._commit_all_boxes()
        if self._current_tool:
            self._current_tool.deactivate()
        self.current_page_idx = idx
        if self._continuous_mode:
            self._update_cont_offsets(idx)
            self._thumb.refresh_all_borders()
            self._thumb.scroll_to_active()
            self._scroll_to_current_cont()
            page = self.doc.get_page(idx)
            self._page_label.config(text=f"{idx+1} / {self.doc.page_count}")
            self._st_size.config(text=f"{int(page.width)} × {int(page.height)} pt")
        else:
            self._thumb.refresh_all_borders()
            self._render()
        if self._current_tool:
            self._current_tool.activate()

    def _thumb_page_click(self, idx: int):
        if self._is_staging_mode:
            self._preview_staging_image(idx)
        else:
            if not self.doc or idx == self.current_page_idx:
                return
            self._navigate_to(idx)

    def _thumb_reorder(self, src_idx, dst_idx):
        if self._is_staging_mode:
            path = self._staging_images.pop(src_idx)
            insert_at = dst_idx if dst_idx <= src_idx else dst_idx - 1
            self._staging_images.insert(insert_at, path)
            self._thumb.reset_for_images(self._staging_images)
            self._preview_staging_image(insert_at)
            self._flash_status(f"↕ Moved image {src_idx+1} → {insert_at+1}")
        else:
            if not self.doc:
                return
            n = self.doc.page_count
            old = list(range(n))
            new = old[:]
            new.pop(src_idx)
            insert_at = dst_idx if dst_idx <= src_idx else dst_idx - 1
            new.insert(insert_at, src_idx)
            if new == old:
                return
            cmd = ReorderPagesCommand(self.doc, new)
            try:
                cmd.execute()
            except Exception as ex:
                cmd.cleanup()
                messagebox.showerror("Reorder Error", str(ex))
                return
            self._push_history(cmd)
            self.current_page_idx = new.index(old[self.current_page_idx]) if self.current_page_idx < n else 0
            self._mark_dirty()
            self._cont_images.clear()
            self._thumb.reset()
            self._render()
            self._flash_status(f"↕ Moved page {src_idx+1} → {insert_at+1}")

    def _thumb_add_page(self, after_idx: int):
        if not self.doc:
            return
        try:
            ref = self.doc.get_page(max(0, after_idx))
            self.doc.insert_page(after_idx + 1, width=ref.width, height=ref.height)
        except Exception as ex:
            messagebox.showerror("Add Page", str(ex))
            return
        self.current_page_idx = after_idx + 1
        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"+ Added page at {after_idx+2}")

    def _thumb_delete_page(self, idx: int):
        if not self.doc:
            return
        if self.doc.page_count <= 1:
            messagebox.showwarning("Cannot Delete", "A PDF must have at least one page.")
            return
        if not messagebox.askyesno("Delete Page",
                                   f"Permanently delete page {idx+1}?", icon="warning"):
            return
        try:
            self.doc.delete_page(idx)
        except Exception as ex:
            messagebox.showerror("Delete", str(ex))
            return
        self.current_page_idx = min(self.current_page_idx, self.doc.page_count - 1)
        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"✕ Deleted page {idx+1}")

    def _thumb_duplicate_page(self, idx: int):
        if not self.doc:
            return
        cmd = DuplicatePageCommand(self.doc, idx)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Duplicate", str(ex))
            return
        self._push_history(cmd)
        self.current_page_idx = idx + 1
        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"⧉ Duplicated page {idx+1}")

    def _thumb_rotate_page(self, idx: int, angle: int):
        if not self.doc:
            return
        cmd = RotatePageCommand(self.page_service, self.doc, idx, angle)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Rotate", str(ex))
            return
        self._push_history(cmd)
        self._thumb.mark_dirty(idx)
        self._cont_invalidate_cache(idx)
        if idx == self.current_page_idx:
            self._render()
        self._flash_status(f"{'↺' if angle < 0 else '↻'} Rotated page {idx+1}")

    def _rotate(self, angle: int):
        if self.doc:
            self._thumb_rotate_page(self.current_page_idx, angle)

    def _add_page(self):
        if self.doc:
            self._thumb_add_page(self.current_page_idx)

    def _delete_page(self):
        if self.doc:
            self._thumb_delete_page(self.current_page_idx)

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _zoom_in(self):
        self._set_zoom(min(MAX_SCALE, self.scale_factor + SCALE_STEP))

    def _zoom_out(self):
        self._set_zoom(max(MIN_SCALE, self.scale_factor - SCALE_STEP))

    def _zoom_reset(self):
        self._set_zoom(RENDER_DPI)

    def _set_zoom(self, s: float):
        self.scale_factor = round(s, 3)
        self._update_zoom_label()
        self._cont_invalidate_cache()
        self._render()

    def _update_zoom_label(self):
        pct = int(self.scale_factor / RENDER_DPI * 100)
        self._zoom_label.config(text=f"{pct}%")
        if hasattr(self, "_st_zoom"):
            self._st_zoom.config(text=f"Zoom {pct}%")

    # ── View mode ─────────────────────────────────────────────────────────────

    def _set_single_mode(self):
        if not self._continuous_mode:
            return
        self._commit_all_boxes()
        self._continuous_mode = False
        self._cont_images.clear()
        self._update_view_mode_buttons()
        self._render()

    def _set_continuous_mode(self):
        if self._continuous_mode:
            return
        self._commit_all_boxes()
        self._continuous_mode = True
        self._update_view_mode_buttons()
        self._render()
        self.root.after(80, self._scroll_to_current_cont)

    def _update_view_mode_buttons(self):
        if not hasattr(self, "_btn_single"):
            return
        if self._continuous_mode:
            self._btn_single.config(fg=PALETTE["fg_dim"],      bg=PALETTE["bg_mid"])
            self._btn_scroll.config(fg=PALETTE["accent_light"], bg=PALETTE["bg_hover"])
        else:
            self._btn_single.config(fg=PALETTE["accent_light"], bg=PALETTE["bg_hover"])
            self._btn_scroll.config(fg=PALETTE["fg_dim"],       bg=PALETTE["bg_mid"])

    # ── Search bar ────────────────────────────────────────────────────────────

    def _toggle_search_bar(self):
        self._search_bar_visible = not self._search_bar_visible
        if self._search_bar_visible:
            self._search_bar_frame.pack(side=tk.TOP, fill=tk.X, before=self.canvas)
            self._sb_entry.focus_set()
            self._sb_entry.select_range(0, tk.END)
            if self.active_tool.get() != "redact":
                self.active_tool.set("redact")
                self._on_tool_change()
        else:
            self._search_bar_frame.pack_forget()
            self._search_bar_clear()

    def _search_bar_find(self):
        if not self.doc:
            return
        query = self._sb_query_var.get().strip()
        if not query:
            self._sb_hit_lbl.config(text="Enter a search term")
            return
        if self.active_tool.get() != "redact":
            self.active_tool.set("redact")
            self._on_tool_change()
        rt = self._get_tool("redact")
        if not rt:
            return
        total = rt.search_all_pages(query, case_sensitive=self._sb_case_var.get())
        if total == 0:
            self._sb_hit_lbl.config(text="No matches")
            for b in (self._sb_prev_btn, self._sb_next_btn,
                      self._sb_redact_one_btn, self._sb_redact_all_btn):
                b.config(state=tk.DISABLED)
            self._flash_status(f'No matches for "{query}"', color=PALETTE["fg_secondary"])

    def _search_bar_next(self):
        rt = self._get_tool("redact")
        if rt:
            rt.navigate_next()

    def _search_bar_prev(self):
        rt = self._get_tool("redact")
        if rt:
            rt.navigate_prev()

    def _search_bar_redact_one(self):
        rt = self._get_tool("redact")
        if rt:
            rt.redact_current_hit()
        if hasattr(self, "_redact_confirm_frame"):
            self._redact_confirm_frame.pack_forget()

    def _search_bar_redact_all(self):
        rt = self._get_tool("redact")
        if rt:
            rt.redact_all_hits()
        if hasattr(self, "_redact_confirm_frame"):
            self._redact_confirm_frame.pack_forget()

    def _search_bar_clear(self):
        rt = self._get_tool("redact")
        if rt and rt.has_search_hits:
            rt.cancel_search()
        self._sb_hit_lbl.config(text="")
        for b in (self._sb_prev_btn, self._sb_next_btn,
                  self._sb_redact_one_btn, self._sb_redact_all_btn):
            b.config(state=tk.DISABLED)

    def _on_search_hit_changed(self, cur_idx: int, total: int):
        if total == 0 or cur_idx < 0:
            self._sb_hit_lbl.config(text="No matches", fg=PALETTE["fg_dim"])
            for b in (self._sb_prev_btn, self._sb_next_btn,
                      self._sb_redact_one_btn, self._sb_redact_all_btn):
                b.config(state=tk.DISABLED)
            return
        rt = self._get_tool("redact")
        page_lbl = f"p.{rt._all_hits[cur_idx][0]+1}" if rt else ""
        self._sb_hit_lbl.config(text=f"{cur_idx+1} of {total}  ({page_lbl})",
                                 fg=PALETTE["fg_primary"])
        can_nav = total > 1
        self._sb_prev_btn.config(state=tk.NORMAL if can_nav else tk.DISABLED)
        self._sb_next_btn.config(state=tk.NORMAL if can_nav else tk.DISABLED)
        self._sb_redact_one_btn.config(state=tk.NORMAL)
        self._sb_redact_all_btn.config(state=tk.NORMAL)
        # Sync properties panel confirm
        if hasattr(self, "_redact_hit_label"):
            self._redact_hit_label.config(text=f"⚠ {total} match(es) across all pages")
            self._redact_confirm_frame.pack(fill=tk.X, pady=(0, 4))

    # ── Tool option callbacks ─────────────────────────────────────────────────

    def _sb_font_change(self):
        self.font_index = PDF_FONT_LABELS.index(self._sb_font_var.get())

    def _sb_size_change(self):
        try:
            self.fontsize = max(6, min(144, int(self._sb_size_var.get())))
        except (ValueError, tk.TclError):
            pass

    def _sb_align_change(self, align: int):
        self.text_align = align
        self._sb_refresh_align()

    def _sb_refresh_align(self):
        for i, btn in enumerate(self._sb_align_btns):
            if i == self.text_align:
                btn.config(bg=PALETTE["accent"], fg=PALETTE["fg_inverse"])
            else:
                btn.config(bg=PALETTE["bg_panel"], fg=PALETTE["fg_secondary"])

    def _pick_global_color(self):
        hex_c = _rgb255_to_hex(self.text_color)
        result = colorchooser.askcolor(color=hex_c, title="Text Color")
        if result and result[0]:
            self.text_color = tuple(int(v) for v in result[0])
            if hasattr(self, "_text_color_swatch"):
                self._text_color_swatch.config(bg=_rgb255_to_hex(self.text_color))

    def _pick_annot_stroke_color(self):
        result = colorchooser.askcolor(color=_rgb255_to_hex(self.annot_stroke_rgb),
                                       title="Annotation Stroke Color")
        if result and result[0]:
            self.annot_stroke_rgb = tuple(int(v) for v in result[0])
            if hasattr(self, "_annot_stroke_sw"):
                self._annot_stroke_sw.config(bg=_rgb255_to_hex(self.annot_stroke_rgb))

    def _on_annot_fill_toggle(self):
        if self._annot_fill_none_var.get():
            self.annot_fill_rgb = None
            self._annot_fill_swatch.config(state=tk.DISABLED)
        else:
            if self.annot_fill_rgb is None:
                self.annot_fill_rgb = (255, 255, 0)
            self._annot_fill_swatch.config(
                bg=_rgb255_to_hex(self.annot_fill_rgb), state=tk.NORMAL)

    def _pick_annot_fill_color(self):
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self.annot_fill_rgb or (255, 255, 0)),
            title="Annotation Fill Color")
        if result and result[0]:
            self.annot_fill_rgb = tuple(int(v) for v in result[0])
            self._annot_fill_swatch.config(bg=_rgb255_to_hex(self.annot_fill_rgb))

    def _on_annot_width_change(self):
        try:
            self.annot_width = max(0.5, min(10.0, float(self._annot_width_var.get())))
        except (ValueError, tk.TclError):
            pass

    def _set_draw_mode(self, mode: str):
        self.draw_mode = mode
        self._refresh_draw_mode_btns()

    def _refresh_draw_mode_btns(self):
        if not hasattr(self, "_draw_mode_btns"):
            return
        for m, btn in self._draw_mode_btns.items():
            if m == self.draw_mode:
                btn.config(bg=PALETTE["accent"], fg=PALETTE["fg_inverse"])
            else:
                btn.config(bg=PALETTE["bg_hover"], fg=PALETTE["fg_secondary"])

    def _pick_draw_stroke_color(self):
        result = colorchooser.askcolor(color=_rgb255_to_hex(self.draw_stroke_rgb),
                                       title="Draw Stroke Color")
        if result and result[0]:
            self.draw_stroke_rgb = tuple(int(v) for v in result[0])
            if hasattr(self, "_draw_stroke_sw"):
                self._draw_stroke_sw.config(bg=_rgb255_to_hex(self.draw_stroke_rgb))

    def _on_draw_fill_toggle(self):
        if self._draw_fill_none_var.get():
            self.draw_fill_rgb = None
            self._draw_fill_swatch.config(state=tk.DISABLED)
        else:
            if self.draw_fill_rgb is None:
                self.draw_fill_rgb = (255, 255, 136)
            self._draw_fill_swatch.config(
                bg=_rgb255_to_hex(self.draw_fill_rgb), state=tk.NORMAL)

    def _pick_draw_fill_color(self):
        result = colorchooser.askcolor(
            color=_rgb255_to_hex(self.draw_fill_rgb or (255, 255, 136)),
            title="Draw Fill Color")
        if result and result[0]:
            self.draw_fill_rgb = tuple(int(v) for v in result[0])
            self._draw_fill_swatch.config(bg=_rgb255_to_hex(self.draw_fill_rgb))

    def _on_draw_width_change(self):
        try:
            self.draw_width = max(0.5, float(self._draw_width_var.get()))
        except (ValueError, tk.TclError):
            pass

    def _on_draw_opacity_change(self):
        try:
            self.draw_opacity = max(0.1, min(1.0, self._draw_opacity_var.get() / 100))
        except (ValueError, tk.TclError):
            pass

    def _pick_redact_fill_color(self):
        r, g, b = [int(v * 255) for v in self.redact_fill_color]
        result = colorchooser.askcolor(color=f"#{r:02x}{g:02x}{b:02x}",
                                       title="Redaction Fill Color")
        if result and result[0]:
            r8, g8, b8 = [int(v) for v in result[0]]
            self.redact_fill_color = (r8/255, g8/255, b8/255)
            if hasattr(self, "_redact_fill_sw"):
                self._redact_fill_sw.config(bg=f"#{r8:02x}{g8:02x}{b8:02x}")

    def _on_redact_label_change(self):
        self.redact_label = self._redact_label_var.get()

    def _redact_find(self):
        rt = self._get_tool("redact")
        if not rt or not self.doc:
            return
        query = self._redact_query_var.get().strip()
        if not query:
            self._flash_status("Enter a search term first", color=PALETTE["fg_secondary"])
            return
        total = rt.search_all_pages(query, case_sensitive=self._redact_case_var.get())
        if total == 0:
            self._redact_confirm_frame.pack_forget()
            self._flash_status(f'No matches for "{query}"', color=PALETTE["fg_secondary"])

    def _redact_confirm(self):
        rt = self._get_tool("redact")
        if rt:
            rt.redact_all_hits()
        if hasattr(self, "_redact_confirm_frame"):
            self._redact_confirm_frame.pack_forget()
        if self._search_bar_visible:
            self._sb_hit_lbl.config(text="")
            for b in (self._sb_redact_one_btn, self._sb_redact_all_btn,
                      self._sb_prev_btn, self._sb_next_btn):
                b.config(state=tk.DISABLED)

    def _redact_cancel_hits(self):
        rt = self._get_tool("redact")
        if rt:
            rt.cancel_search()
        if hasattr(self, "_redact_confirm_frame"):
            self._redact_confirm_frame.pack_forget()
        if self._search_bar_visible:
            self._sb_hit_lbl.config(text="")
            for b in (self._sb_redact_one_btn, self._sb_redact_all_btn,
                      self._sb_prev_btn, self._sb_next_btn):
                b.config(state=tk.DISABLED)
        self._flash_status("Redaction cancelled", color=PALETTE["fg_secondary"])

    def _on_draw_committed(self, page_idx: int, xref: int):
        cmd = DrawAnnotationCommand(self.doc, page_idx, xref)
        self._push_history(cmd)
        self._mark_dirty()
        self._cont_invalidate_cache(page_idx)
        self._thumb.mark_dirty(page_idx)
        if page_idx == self.current_page_idx:
            self._render()
        elif self._continuous_mode:
            self._render_cont_page_refresh(page_idx)

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self):
        if not self.doc:
            return
        if self._continuous_mode:
            self._render_continuous()
        else:
            self._render_single()

    def _render_single(self):
        page = self.doc.get_page(self.current_page_idx)
        ppm  = page.render_to_ppm(scale=self.scale_factor)
        self.tk_image = tk.PhotoImage(data=ppm)
        iw = int(page.width  * self.scale_factor)
        ih = int(page.height * self.scale_factor)
        cw = self.canvas.winfo_width()
        self._page_offset_x = max(PAD_XL, (cw - iw) // 2)
        self._page_offset_y = PAD_XL
        ox, oy = self._page_offset_x, self._page_offset_y
        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")
        self.canvas.delete("page_bg")
        self.canvas.delete("textsel")
        # Subtle shadow
        self.canvas.create_rectangle(
            ox+4, oy+4, ox+iw+4, oy+ih+4,
            fill=PALETTE["page_shadow"], outline="", stipple="gray25", tags="page_shadow")
        self.canvas.create_image(ox, oy, anchor=tk.NW, image=self.tk_image, tags="page_img")
        self.canvas.config(scrollregion=(0, 0, ox+iw+50, oy+ih+50))
        self._page_label.config(text=f"{self.current_page_idx+1} / {self.doc.page_count}")
        self._st_size.config(text=f"{int(page.width)} × {int(page.height)} pt")
        for box in list(self._text_boxes):
            box.rescale(self.scale_factor, self._page_offset_x, self._page_offset_y)
        self._thumb.refresh_all_borders()
        self._thumb.scroll_to_active()
        if self.active_tool.get() == "select_text":
            sel = self._get_tool("select_text")
            if sel:
                sel.reload()

    _CONT_GAP = 20

    def _cont_page_top(self, idx: int) -> int:
        doc = self.doc
        if not doc:
            return 0
        y = self._CONT_GAP
        for i in range(idx):
            p  = doc.get_page(i)
            ih = int(p.height * self.scale_factor)
            y += ih + self._CONT_GAP
        return y

    def _cont_page_at_y(self, canvas_y: float) -> int:
        doc = self.doc
        if not doc:
            return 0
        y = self._CONT_GAP
        for i in range(doc.page_count):
            p  = doc.get_page(i)
            ih = int(p.height * self.scale_factor)
            if canvas_y <= y + ih:
                return i
            y += ih + self._CONT_GAP
        return doc.page_count - 1

    def _render_continuous(self):
        if self._cont_after_id:
            self.root.after_cancel(self._cont_after_id)
            self._cont_after_id = None
        doc = self.doc
        n   = doc.page_count
        cw  = self.canvas.winfo_width()
        total_h = self._CONT_GAP
        max_iw  = 0
        heights, widths = [], []
        for i in range(n):
            p  = doc.get_page(i)
            iw = int(p.width  * self.scale_factor)
            ih = int(p.height * self.scale_factor)
            heights.append(ih); widths.append(iw)
            max_iw = max(max_iw, iw)
            total_h += ih + self._CONT_GAP
        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")
        self.canvas.delete("page_bg")
        self.canvas.delete("textsel")
        self.canvas.config(scrollregion=(0, 0, max(cw, max_iw + 80), total_h))
        y = self._CONT_GAP
        for i in range(n):
            iw, ih = widths[i], heights[i]
            ox = max(PAD_XL, (cw - iw) // 2)
            self.canvas.create_rectangle(
                ox, y, ox+iw, y+ih,
                fill=PALETTE.get("page_bg", "#FFFFFF"), outline="",
                tags=("page_bg", f"page_bg_{i}"))
            self.canvas.create_rectangle(
                ox+4, y+4, ox+iw+4, y+ih+4,
                fill=PALETTE["page_shadow"], outline="", stipple="gray25",
                tags=("page_shadow", f"page_shadow_{i}"))
            self.canvas.tag_lower(f"page_shadow_{i}", f"page_bg_{i}")
            y += ih + self._CONT_GAP
        self._update_cont_offsets(self.current_page_idx)
        cur = self.current_page_idx
        order = [cur]
        for delta in range(1, n):
            if cur - delta >= 0:     order.append(cur - delta)
            if cur + delta < n:      order.append(cur + delta)

        def _render_one(remaining):
            if not remaining or not self.doc:
                self._cont_after_id = None
                return
            idx  = remaining[0]
            rest = remaining[1:]
            self._render_cont_page(idx, widths[idx], heights[idx], cw)
            self._cont_after_id = self.root.after_idle(lambda: _render_one(rest))

        _render_one(order)
        cur_page = doc.get_page(self.current_page_idx)
        self._page_label.config(text=f"{self.current_page_idx+1} / {n}")
        self._st_size.config(text=f"{int(cur_page.width)} × {int(cur_page.height)} pt")
        self._thumb.refresh_all_borders()
        self._thumb.scroll_to_active()

    def _render_cont_page(self, idx, iw, ih, cw):
        doc = self.doc
        if not doc or idx >= doc.page_count:
            return
        key = (idx, self.scale_factor)
        if key not in self._cont_images:
            try:
                page = doc.get_page(idx)
                ppm  = page.render_to_ppm(scale=self.scale_factor)
                self._cont_images[key] = tk.PhotoImage(data=ppm)
            except Exception:
                return
        img = self._cont_images[key]
        y   = self._cont_page_top(idx)
        ox  = max(PAD_XL, (cw - iw) // 2)
        self.canvas.delete(f"page_img_{idx}")
        self.canvas.create_image(ox, y, anchor=tk.NW, image=img,
                                 tags=("page_img", f"page_img_{idx}"))
        self.canvas.tag_lower(f"page_bg_{idx}", f"page_img_{idx}")

    def _render_cont_page_refresh(self, page_idx: int):
        if not self.doc or not self._continuous_mode:
            return
        p  = self.doc.get_page(page_idx)
        iw = int(p.width  * self.scale_factor)
        ih = int(p.height * self.scale_factor)
        cw = self.canvas.winfo_width()
        self._render_cont_page(page_idx, iw, ih, cw)

    def _update_cont_offsets(self, idx: int):
        doc = self.doc
        if not doc:
            return
        p   = doc.get_page(idx)
        iw  = int(p.width * self.scale_factor)
        cw  = self.canvas.winfo_width()
        self._page_offset_x = max(PAD_XL, (cw - iw) // 2)
        self._page_offset_y = self._cont_page_top(idx)

    def _cont_invalidate_cache(self, page_idx=None):
        if page_idx is None:
            self._cont_images.clear()
        else:
            for k in [k for k in self._cont_images if k[0] == page_idx]:
                del self._cont_images[k]

    def _on_cont_scroll(self):
        self._scroll_after_id = None
        if not self.doc or not self._continuous_mode:
            return
        top    = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        mid    = (top + bottom) / 2
        idx    = self._cont_page_at_y(mid)
        if idx != self.current_page_idx:
            self.current_page_idx = idx
            self._update_cont_offsets(idx)
            page = self.doc.get_page(idx)
            self._page_label.config(text=f"{idx+1} / {self.doc.page_count}")
            self._st_size.config(text=f"{int(page.width)} × {int(page.height)} pt")
            self._thumb.refresh_all_borders()
            self._thumb.scroll_to_active()

    def _scroll_to_current_cont(self):
        if not self.doc:
            return
        y_top   = self._cont_page_top(self.current_page_idx)
        total_h = self._cont_page_top(self.doc.page_count)
        if total_h > 0:
            frac = max(0.0, (y_top - self._CONT_GAP) / total_h)
            self.canvas.yview_moveto(frac)

    # ── Canvas events ─────────────────────────────────────────────────────────

    def _canvas_to_pdf(self, cx, cy):
        if self._continuous_mode:
            idx = self._cont_page_at_y(cy)
            if idx != self.current_page_idx:
                self.current_page_idx = idx
                self._update_cont_offsets(idx)
                self._thumb.refresh_all_borders()
                self._thumb.scroll_to_active()
                page = self.doc.get_page(idx)
                self._page_label.config(text=f"{idx+1} / {self.doc.page_count}")
        return (
            (cx - self._page_offset_x) / self.scale_factor,
            (cy - self._page_offset_y) / self.scale_factor,
        )

    def _on_canvas_click(self, event):
        if not self.doc:
            return
        if self._suppress_next_click:
            self._suppress_next_click = False
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        tool = self.active_tool.get()
        if tool == "text":
            pdf_x, pdf_y = self._canvas_to_pdf(cx, cy)
            self._spawn_textbox(pdf_x, pdf_y)
        else:
            t = self._get_tool(tool)
            if t:
                t.on_click(cx, cy)

    def _on_canvas_drag(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        t  = self._get_tool(self.active_tool.get())
        if t:
            t.on_drag(cx, cy)

    def _on_canvas_release(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        t  = self._get_tool(self.active_tool.get())
        if t:
            t.on_release(cx, cy)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")
        if self._continuous_mode:
            if self._scroll_after_id:
                self.root.after_cancel(self._scroll_after_id)
            self._scroll_after_id = self.root.after(80, self._on_cont_scroll)

    def _on_ctrl_scroll(self, event):
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self._zoom_in()
        else:
            self._zoom_out()

    def _on_mouse_motion(self, event):
        if not self.doc:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px, py = self._canvas_to_pdf(cx, cy)
        self._st_coords.config(text=f"x: {px:6.1f}   y: {py:6.1f}")
        if self.active_tool.get() == "select_text":
            t = self._get_tool("select_text")
            if t:
                t.on_motion(cx, cy)

    # ── Text box lifecycle ────────────────────────────────────────────────────

    def _spawn_textbox(self, pdf_x, pdf_y):
        page  = self.doc.get_page(self.current_page_idx)
        pdf_w = page.width * 0.42
        pdf_h = self.fontsize * 4
        bg    = self._sample_page_color(pdf_x, pdf_y)
        box   = TextBox(
            canvas=self.canvas,
            pdf_x=pdf_x, pdf_y=pdf_y,
            pdf_w=pdf_w, pdf_h=pdf_h,
            scale=self.scale_factor,
            page_offset_x=self._page_offset_x,
            page_offset_y=self._page_offset_y,
            font_index=self.font_index,
            fontsize=self.fontsize,
            color_rgb=self.text_color,
            entry_bg=bg,
            align=self.text_align,
            on_commit=self._on_box_confirmed,
            on_delete=self._on_box_deleted,
            on_interact=self._on_box_interact,
        )
        self._text_boxes.append(box)

    def _sample_page_color(self, pdf_x, pdf_y) -> str:
        if self.tk_image is None:
            return self.canvas.cget("bg")
        try:
            ix = int(pdf_x * self.scale_factor)
            iy = int(pdf_y * self.scale_factor)
            r, g, b = self.tk_image.get(ix, iy)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return self.canvas.cget("bg")

    def _on_box_confirmed(self, box: TextBox):
        self._text_boxes = [b for b in self._text_boxes if b is not box]
        text = box.get_text()
        if not text:
            return
        rect = (box.pdf_x, box.pdf_y, box.pdf_x + box.pdf_w, box.pdf_y + box.pdf_h)
        cmd  = InsertTextBoxCommand(
            self.text_service, self.doc,
            self.current_page_idx, rect, text,
            box.fontsize, box.pdf_font_name, box.pdf_color, box.align,
        )
        try:
            cmd.execute()
            self._push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Insert Error", str(ex))
            return
        self._render()

    def _on_box_interact(self):
        self._suppress_next_click = True

    def _on_box_deleted(self, box: TextBox):
        self._text_boxes = [b for b in self._text_boxes if b is not box]

    def _commit_all_boxes(self):
        for box in list(self._text_boxes):
            box._confirm()
        self._text_boxes.clear()

    def _dismiss_boxes(self):
        for box in list(self._text_boxes):
            box._delete()
        self._text_boxes.clear()

    def _copy_selected_text(self):
        t = self._get_tool("select_text")
        if t:
            t.copy()

    # ── History ───────────────────────────────────────────────────────────────

    def _push_history(self, cmd):
        self._history.push(cmd)
        self._thumb.mark_dirty(self.current_page_idx)
        self._cont_invalidate_cache(self.current_page_idx)

    def _on_history_change(self):
        self._mark_dirty()

    def _undo(self):
        if not self._history.can_undo:
            self._flash_status("Nothing to undo", color=PALETTE["fg_secondary"])
            return
        try:
            label = self._history.undo()
            self._thumb.mark_dirty(self.current_page_idx)
            self._cont_invalidate_cache(self.current_page_idx)
            self._render()
            self._flash_status(f"↩ Undid {label}")
        except Exception as ex:
            messagebox.showerror("Undo Error", str(ex))

    def _redo(self):
        if not self._history.can_redo:
            self._flash_status("Nothing to redo", color=PALETTE["fg_secondary"])
            return
        try:
            label = self._history.redo()
            self._thumb.mark_dirty(self.current_page_idx)
            self._cont_invalidate_cache(self.current_page_idx)
            self._render()
            self._flash_status(f"↪ Redid {label}")
        except Exception as ex:
            messagebox.showerror("Redo Error", str(ex))

    # ── Status & title ────────────────────────────────────────────────────────

    def _flash_status(self, message, color=None, duration_ms=3000):
        if color is None:
            color = PALETTE["success"]
        self._st_action.config(text=message, fg=color)
        if hasattr(self, "_flash_after_id") and self._flash_after_id:
            self.root.after_cancel(self._flash_after_id)
        self._flash_after_id = self.root.after(
            duration_ms, lambda: self._st_action.config(text=""))

    def _update_title(self):
        if self._current_path:
            name   = os.path.basename(self._current_path)
            marker = " •" if self._unsaved_changes else ""
            title  = f"{name}{marker}"
        else:
            title = "PDF Editor" + (" — Untitled •" if self._unsaved_changes else "")
        self.root.title(f"PDF Editor — {title}" if self._current_path else title)
        if hasattr(self, "_title_lbl"):
            self._title_lbl.config(
                text=os.path.basename(self._current_path) + (" •" if self._unsaved_changes else "")
                if self._current_path else "PDF Editor"
            )

    def _mark_dirty(self):
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    # ── Escape ────────────────────────────────────────────────────────────────

    def _on_escape(self):
        if self._search_bar_visible:
            self._toggle_search_bar()
        elif self._is_staging_mode:
            self._exit_staging_mode()
        else:
            self._dismiss_boxes()

    # ── Closing ───────────────────────────────────────────────────────────────

    def _on_closing(self):
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes",
                                            "Save before closing?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        self._commit_all_boxes()
        if self._current_tool:
            self._current_tool.deactivate()
        if hasattr(self._thumb, "_after_id") and self._thumb._after_id:
            self.root.after_cancel(self._thumb._after_id)
        self._history.clear()
        if self.doc:
            self.doc.close()
        self.root.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    InteractivePDFEditor(root)
    root.mainloop()