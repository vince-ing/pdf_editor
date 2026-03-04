"""
PDF Editor — Main Window (refactored).

InteractivePDFEditor is now a thin coordinator:
  • Builds the top-bar, sidebar, canvas area, and status bar.
  • Delegates undo/redo to HistoryManager.
  • Delegates thumbnail rendering to ThumbnailPanel.
  • Delegates canvas-tool logic to individual Tool classes.
  • Owns the AppContext namespace that tools use to reach shared state.
"""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser

from src.core.document import PDFDocument
from src.services.page_service import PageService
from src.services.image_service import ImageService
from src.services.text_service import TextService
from src.services.annotation_service import AnnotationService
from src.services.redaction_service import RedactionService

from src.commands.insert_text import InsertTextBoxCommand
from src.commands.rotate_page import RotatePageCommand
from src.commands.page_ops import ReorderPagesCommand, DuplicatePageCommand

from src.gui.theme import (
    PALETTE, FONT_MONO, FONT_UI, FONT_LABEL,
    PDF_FONTS, PDF_FONT_LABELS, TK_FONT_MAP,
    RENDER_DPI, MIN_SCALE, MAX_SCALE, SCALE_STEP,
)
from src.gui.history_manager import HistoryManager
from src.gui.widgets.tooltip import Tooltip
from src.gui.widgets.text_box import TextBox
from src.gui.panels.thumbnail import ThumbnailPanel
from src.gui.tools.annot_tool import AnnotationTool
from src.gui.tools.image_tool import ImageInsertTool, ImageExtractTool
from src.gui.tools.select_tool import SelectTextTool
from src.gui.tools.redact_tool import RedactTool
from src.utils.recent_files import RecentFiles


# ── AppContext ────────────────────────────────────────────────────────────────

class AppContext:
    """
    Lightweight namespace passed to tool classes so they can reach shared
    application state without holding a reference to the full editor class.
    """

    def __init__(self, editor: "InteractivePDFEditor"):
        self._editor = editor

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

    def canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        return self._editor._canvas_to_pdf(cx, cy)

    def push_history(self, cmd):
        self._editor._push_history(cmd)

    def render(self):
        self._editor._render()

    def flash_status(self, message: str, color: str = None, duration_ms: int = 3000):
        self._editor._flash_status(message, color, duration_ms)


# ══════════════════════════════════════════════════════════════════════════════
#  InteractivePDFEditor
# ══════════════════════════════════════════════════════════════════════════════

class InteractivePDFEditor:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF Editor")
        self.root.geometry("1200x820")
        self.root.minsize(800, 600)
        self.root.configure(bg=PALETTE["bg_dark"])

        # Document state
        self.doc: PDFDocument | None = None
        self.current_page_idx = 0
        self.scale_factor     = RENDER_DPI
        self.tk_image         = None
        self._page_offset_x   = 20
        self._page_offset_y   = 20
        self._continuous_mode = True          # default: continuous scroll
        self._cont_images: dict = {}          # (page_idx, scale) → PhotoImage
        self._cont_after_id    = None         # lazy render scheduling
        self._scroll_after_id  = None         # scroll debounce
        self._current_path: str | None = None
        self._unsaved_changes = False

        # Services
        self.page_service       = PageService()
        self.text_service       = TextService()
        self.image_service      = ImageService()
        self.annotation_service = AnnotationService()
        self.redaction_service  = RedactionService()

        # Annotation style state (used by AnnotationTool via getters)
        self.annot_stroke_rgb: tuple       = (220, 50, 50)
        self.annot_fill_rgb: tuple | None  = None
        self.annot_width: float            = 1.5

        # Redaction state
        self.redact_fill_color: tuple  = (0.0, 0.0, 0.0)   # black (0-1 floats)
        self.redact_label: str         = ""                 # replacement text

        # Text defaults
        self.active_tool = tk.StringVar(value="text")
        self.font_index  = 0
        self.fontsize    = 14
        self.text_color  = (0, 0, 0)
        self.text_align  = 0

        # Active text boxes
        self._text_boxes: list[TextBox] = []
        self._suppress_next_click = False

        # History
        self._history = HistoryManager(on_change=self._on_history_change)

        # Recent files
        self._recent = RecentFiles()

        # Search bar state
        self._search_bar_visible = False
        self._search_bar_frame   = None   # set in _build_canvas_area

        # Build UI
        self._build_ui()
        self._apply_ttk_style()

        # AppContext (after UI so canvas exists)
        self._ctx = AppContext(self)

        # Tools (after context)
        self._tools: dict = {}
        self._current_tool = None
        self._init_tools()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ── tool initialisation ───────────────────────────────────────────────────

    def _init_tools(self):
        ctx = self._ctx
        self._tools["highlight"] = AnnotationTool(
            ctx, self.annotation_service, "highlight",
            get_stroke_rgb=lambda: self.annot_stroke_rgb,
            get_fill_rgb=lambda: self.annot_fill_rgb,
            get_width=lambda: self.annot_width,
        )
        self._tools["rect_annot"] = AnnotationTool(
            ctx, self.annotation_service, "rect_annot",
            get_stroke_rgb=lambda: self.annot_stroke_rgb,
            get_fill_rgb=lambda: self.annot_fill_rgb,
            get_width=lambda: self.annot_width,
        )
        self._tools["insert_image"] = ImageInsertTool(
            ctx, self.image_service,
            set_hint=lambda t: self._hint.config(text=t, fg=PALETTE["fg_dim"]),
        )
        self._tools["extract"] = ImageExtractTool(ctx, self.image_service)
        self._tools["select_text"] = SelectTextTool(ctx, self.root)
        self._tools["redact"] = RedactTool(
            ctx, self.redaction_service,
            get_fill_color=lambda: self.redact_fill_color,
            get_replacement_text=lambda: self.redact_label,
            on_navigate_page=self._navigate_to,
            on_hit_changed=self._on_search_hit_changed,
        )

    def _get_tool(self, name: str):
        return self._tools.get(name)

    # ── TTK style ─────────────────────────────────────────────────────────────

    def _apply_ttk_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TCombobox",
                        fieldbackground="#252535", background="#252535",
                        foreground=PALETTE["fg_primary"],
                        selectbackground=PALETTE["accent_dim"],
                        selectforeground=PALETTE["fg_primary"],
                        bordercolor=PALETTE["border"],
                        lightcolor=PALETTE["border"],
                        darkcolor=PALETTE["border"])
        style.map("TCombobox",
                  fieldbackground=[("readonly", "#252535")],
                  selectbackground=[("readonly", PALETTE["accent_dim"])],
                  selectforeground=[("readonly", PALETTE["fg_primary"])])
        for orient in ("Vertical", "Horizontal"):
            style.configure(f"{orient}.TScrollbar",
                            background=PALETTE["bg_panel"],
                            troughcolor=PALETTE["bg_dark"],
                            bordercolor=PALETTE["border"],
                            arrowcolor=PALETTE["fg_dim"])

    # ── UI build ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        body.pack(fill=tk.BOTH, expand=True)
        self._build_sidebar(body)
        # ThumbnailPanel is packed RIGHT before canvas
        self._thumb = ThumbnailPanel(
            parent=body,
            get_doc=lambda: self.doc,
            get_current_page=lambda: self.current_page_idx,
            on_page_click=self._thumb_page_click,
            root=self.root,
            on_reorder=self._thumb_reorder,
            on_add_page=self._thumb_add_page,
            on_delete_page=self._thumb_delete_page,
            on_duplicate_page=self._thumb_duplicate_page,
            on_rotate_page=self._thumb_rotate_page,
        )
        self._build_canvas_area(body)
        self._build_statusbar()
        # Initialise startup screen state
        self._startup_frame = None
        # Populate the recent ▾ dropdown and show welcome screen
        self.root.after(50, self._rebuild_recent_menu)
        self.root.after(60, self._show_startup_screen)

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["bg_mid"], height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="◼ PDF Editor", bg=PALETTE["bg_mid"],
                 fg=PALETTE["accent_light"],
                 font=("Helvetica", 13, "bold"), padx=16).pack(side=tk.LEFT)

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)

        for label, cmd, tip in [
            ("📂  Open",    self._open_pdf,    "Open PDF  (Ctrl+O)"),
            ("💾  Save",    self._save_pdf,    "Save PDF  (Ctrl+S)"),
            ("📋  Save As", self._save_pdf_as, "Save PDF as new file  (Ctrl+Shift+S)"),
            ("↩  Undo",    self._undo,         "Undo last action  (Ctrl+Z)"),
            ("↪  Redo",    self._redo,         "Redo last undone action  (Ctrl+Y)"),
        ]:
            Tooltip(self._topbar_btn(bar, label, cmd), tip)

        # Recent files dropdown — sits immediately after Open
        self._recent_mb = tk.Menubutton(
            bar, text="▾",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica", 9), relief="flat", bd=0,
            padx=4, pady=0, cursor="hand2",
            highlightthickness=0,
        )
        self._recent_mb.pack(side=tk.LEFT, fill=tk.Y)
        Tooltip(self._recent_mb, "Recent files")

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)

        tk.Label(bar, text="Zoom:", bg=PALETTE["bg_mid"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL, padx=8).pack(side=tk.LEFT)
        self._zoom_label = tk.Label(bar, text="100%", bg=PALETTE["bg_mid"],
                                    fg=PALETTE["fg_primary"], font=FONT_MONO, width=5)
        self._zoom_label.pack(side=tk.LEFT)
        Tooltip(self._topbar_btn(bar, "−", self._zoom_out), "Zoom out  (Ctrl+−)")
        Tooltip(self._topbar_btn(bar, "+", self._zoom_in),  "Zoom in   (Ctrl+=)")
        Tooltip(self._topbar_btn(bar, "⟳", self._zoom_reset), "Reset zoom  (Ctrl+0)")

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)

        # ── View mode toggle ──────────────────────────────────────────────
        tk.Label(bar, text="View:", bg=PALETTE["bg_mid"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL, padx=8).pack(side=tk.LEFT)

        self._btn_single = self._topbar_btn(bar, "□ Single", self._set_single_mode)
        self._btn_scroll = self._topbar_btn(bar, "▤ Scroll", self._set_continuous_mode)
        Tooltip(self._btn_single, "Single page view")
        Tooltip(self._btn_scroll, "Continuous scroll view")
        self._update_view_mode_buttons()

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)
        Tooltip(
            self._topbar_btn(bar, "🔍  Find & Redact", self._toggle_search_bar),
            "Search & redact text on this page  (Ctrl+F)",
        )

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(side=tk.LEFT, fill=tk.Y, pady=8)
        self._thumb_toggle_btn = self._topbar_btn(bar, "⊞  Pages", self._toggle_thumb_panel)
        Tooltip(self._thumb_toggle_btn, "Show / hide page thumbnails  (Ctrl+T)")

        self._update_zoom_label()
        self._thumb_visible = True

        self.root.bind("<Control-t>",     lambda e: self._toggle_thumb_panel())
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
        # Global Ctrl+F → show search bar
        self.root.bind("<Control-f>",     lambda e: self._toggle_search_bar())
        self.root.bind("<F3>",            lambda e: self._search_bar_next())
        self.root.bind("<Shift-F3>",      lambda e: self._search_bar_prev())

    def _topbar_btn(self, parent, text, cmd) -> tk.Button:
        btn = tk.Button(parent, text=text, command=cmd,
                        bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
                        activebackground=PALETTE["bg_hover"],
                        activeforeground=PALETTE["accent_light"],
                        font=("Helvetica", 10), relief="flat", bd=0,
                        padx=12, pady=0, cursor="hand2", highlightthickness=0)
        btn.pack(side=tk.LEFT, fill=tk.Y)
        return btn

    def _build_sidebar(self, parent):
        sb = tk.Frame(parent, bg=PALETTE["bg_panel"], width=196)
        sb.pack(side=tk.LEFT, fill=tk.Y)
        sb.pack_propagate(False)

        self._section(sb, "NAVIGATION")
        nav = tk.Frame(sb, bg=PALETTE["bg_panel"])
        nav.pack(fill=tk.X, padx=12, pady=6)
        self._sb_mini_btn(nav, "◀", self._prev_page).pack(side=tk.LEFT)
        self._page_label = tk.Label(nav, text="—", bg=PALETTE["bg_panel"],
                                    fg=PALETTE["fg_primary"], font=FONT_UI)
        self._page_label.pack(side=tk.LEFT, expand=True)
        self._sb_mini_btn(nav, "▶", self._next_page).pack(side=tk.RIGHT)

        self._section(sb, "PAGE ACTIONS")
        self._sb_btn(sb, "↺  Rotate Left",  lambda: self._rotate(-90))
        self._sb_btn(sb, "↻  Rotate Right", lambda: self._rotate(90))
        self._sb_btn(sb, "+  Add Page",      self._add_page)
        self._sb_btn(sb, "✕  Delete Page",  self._delete_page)

        self._section(sb, "ACTIVE TOOL")
        for label, val, tip in [
            ("📝  Text",          "text",         "Click canvas to add a text box"),
            ("🖼  Extract Image", "extract",      "Click an image to save it"),
            ("📌  Insert Image",  "insert_image", "Choose a file then drag to place it"),
            ("🖍  Highlight",     "highlight",    "Drag to highlight a region"),
            ("▭  Rectangle",     "rect_annot",   "Drag to draw a rectangle annotation"),
            ("⬚  Select Text",   "select_text",  "Click or drag to select & copy text"),
            ("⬛  Redact",        "redact",       "Drag to permanently redact content"),
        ]:
            rb = tk.Radiobutton(sb, text=label, variable=self.active_tool, value=val,
                                bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                                selectcolor=PALETTE["accent_dim"],
                                activebackground=PALETTE["bg_hover"],
                                activeforeground=PALETTE["accent_light"],
                                font=FONT_UI, anchor="w", cursor="hand2",
                                command=self._on_tool_change)
            rb.pack(fill=tk.X, padx=12, pady=2)
            Tooltip(rb, tip)

        self._section(sb, "TEXT DEFAULTS")
        self._txt_opts = tk.Frame(sb, bg=PALETTE["bg_panel"])
        self._txt_opts.pack(fill=tk.X, padx=12, pady=4)
        self._build_text_opts(self._txt_opts)

        self._annot_opts = tk.Frame(sb, bg=PALETTE["bg_panel"])
        self._build_annot_opts(self._annot_opts)

        self._redact_opts = tk.Frame(sb, bg=PALETTE["bg_panel"])
        self._build_redact_opts(self._redact_opts)

        self._hint = tk.Label(sb,
            text="Click canvas to place a text box.\n"
                 "Drag the ◢ grip to move.\n"
                 "Ctrl+Z to undo after confirming.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=FONT_LABEL, justify="center", wraplength=176)
        self._hint.pack(side=tk.BOTTOM, pady=14)

    def _build_text_opts(self, parent):
        self._opt_lbl(parent, "Font")
        self._sb_font_var = tk.StringVar(value=PDF_FONT_LABELS[self.font_index])
        fc = ttk.Combobox(parent, textvariable=self._sb_font_var,
                          values=PDF_FONT_LABELS, state="readonly", width=18)
        fc.pack(fill=tk.X, pady=(0, 8))
        fc.bind("<<ComboboxSelected>>", lambda _: self._sb_font_change())

        self._opt_lbl(parent, "Size (pt)")
        self._sb_size_var = tk.IntVar(value=self.fontsize)
        tk.Spinbox(parent, from_=6, to=144, textvariable=self._sb_size_var,
                   width=6, command=self._sb_size_change,
                   bg="#252535", fg=PALETTE["fg_primary"],
                   buttonbackground=PALETTE["border"],
                   relief="flat", highlightthickness=0).pack(anchor="w", pady=(0, 8))

        self._opt_lbl(parent, "Color")
        color_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        color_row.pack(fill=tk.X, pady=(0, 8))
        self._color_swatch = tk.Button(
            color_row, text="  ", relief="flat", bd=1, width=3,
            bg="#000000", cursor="hand2", command=self._pick_global_color,
            highlightthickness=1, highlightbackground="#555")
        self._color_swatch.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(color_row, text="Pick color", bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(side=tk.LEFT)

        self._opt_lbl(parent, "Alignment")
        align_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        align_row.pack(fill=tk.X, pady=(0, 4))
        self._sb_align_btns = []
        for idx, (symbol, tip) in enumerate([("≡L", "Left"), ("≡C", "Center"),
                                              ("≡R", "Right"), ("≡J", "Justify")]):
            btn = tk.Button(
                align_row, text=symbol, width=3,
                font=("Helvetica", 8), relief="flat", bd=0,
                padx=3, pady=2, cursor="hand2",
                command=lambda i=idx: self._sb_align_change(i),
            )
            btn.pack(side=tk.LEFT, padx=1)
            Tooltip(btn, tip)
            self._sb_align_btns.append(btn)
        self._sb_refresh_align()

    def _build_annot_opts(self, parent):
        self._opt_lbl(parent, "Stroke Color")
        stroke_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        stroke_row.pack(fill=tk.X, pady=(0, 8))
        self._annot_stroke_swatch = tk.Button(
            stroke_row, text="  ", relief="flat", bd=1, width=3,
            bg=self._rgb255_to_hex(self.annot_stroke_rgb),
            cursor="hand2", command=self._pick_annot_stroke_color,
            highlightthickness=1, highlightbackground="#555",
        )
        self._annot_stroke_swatch.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(stroke_row, text="Pick color", bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(side=tk.LEFT)

        self._opt_lbl(parent, "Fill Color")
        fill_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        fill_row.pack(fill=tk.X, pady=(0, 8))
        self._annot_fill_none_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            fill_row, text="No fill", variable=self._annot_fill_none_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            selectcolor=PALETTE["accent_dim"],
            activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2",
            command=self._on_annot_fill_toggle,
        ).pack(side=tk.LEFT)
        self._annot_fill_swatch = tk.Button(
            fill_row, text="  ", relief="flat", bd=1, width=3,
            bg="#FFFF00", cursor="hand2", command=self._pick_annot_fill_color,
            highlightthickness=1, highlightbackground="#555",
            state=tk.DISABLED,
        )
        self._annot_fill_swatch.pack(side=tk.LEFT, padx=(8, 0))

        self._opt_lbl(parent, "Stroke Width")
        self._annot_width_var = tk.DoubleVar(value=self.annot_width)
        width_sp = tk.Spinbox(
            parent, from_=0.5, to=10.0, increment=0.5,
            textvariable=self._annot_width_var, width=6,
            command=self._on_annot_width_change,
            bg="#252535", fg=PALETTE["fg_primary"],
            buttonbackground=PALETTE["border"],
            relief="flat", highlightthickness=0,
        )
        width_sp.pack(anchor="w", pady=(0, 4))
        width_sp.bind("<Return>", lambda e: self._on_annot_width_change())

    def _build_redact_opts(self, parent):
        """Sidebar panel shown when the Redact tool is active."""
        self._opt_lbl(parent, "Fill Color")
        fill_row = tk.Frame(parent, bg=PALETTE["bg_panel"])
        fill_row.pack(fill=tk.X, pady=(0, 8))

        def _fill_hex():
            r, g, b = [int(v * 255) for v in self.redact_fill_color]
            return f"#{r:02x}{g:02x}{b:02x}"

        self._redact_fill_swatch = tk.Button(
            fill_row, text="  ", relief="flat", bd=1, width=3,
            bg=_fill_hex(), cursor="hand2",
            command=self._pick_redact_fill_color,
            highlightthickness=1, highlightbackground="#555",
        )
        self._redact_fill_swatch.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(fill_row, text="Pick color", bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(side=tk.LEFT)

        self._opt_lbl(parent, "Replacement Label")
        self._redact_label_var = tk.StringVar(value=self.redact_label)
        lbl_entry = tk.Entry(
            parent, textvariable=self._redact_label_var,
            bg="#252535", fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["border"], width=16,
        )
        lbl_entry.pack(fill=tk.X, pady=(0, 4))
        lbl_entry.bind("<KeyRelease>", lambda e: self._on_redact_label_change())
        tk.Label(parent, text='e.g. "[REDACTED]" or leave blank',
                 bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                 font=("Helvetica", 7), wraplength=160).pack(anchor="w", pady=(0, 10))

        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(0, 8))
        self._opt_lbl(parent, "Search & Redact")

        self._redact_query_var = tk.StringVar()
        query_entry = tk.Entry(
            parent, textvariable=self._redact_query_var,
            bg="#252535", fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["border"], width=16,
        )
        query_entry.pack(fill=tk.X, pady=(0, 4))
        query_entry.bind("<Return>", lambda e: self._redact_find())

        self._redact_case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            parent, text="Case-sensitive",
            variable=self._redact_case_var,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            selectcolor=PALETTE["accent_dim"],
            activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2",
        ).pack(anchor="w", pady=(0, 6))

        self._redact_find_btn = tk.Button(
            parent, text="🔍  Find on Page",
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
            activebackground=PALETTE["accent_dim"],
            font=FONT_LABEL, relief="flat", bd=0,
            padx=8, pady=4, cursor="hand2",
            command=self._redact_find,
        )
        self._redact_find_btn.pack(fill=tk.X, pady=(0, 4))

        self._redact_confirm_frame = tk.Frame(parent, bg=PALETTE["bg_panel"])
        self._redact_confirm_frame.pack(fill=tk.X, pady=(0, 4))
        self._redact_confirm_frame.pack_forget()

        self._redact_hit_label = tk.Label(
            self._redact_confirm_frame, text="",
            bg=PALETTE["bg_panel"], fg=PALETTE["danger"],
            font=("Helvetica", 8, "bold"),
        )
        self._redact_hit_label.pack(anchor="w", pady=(0, 4))

        tk.Button(
            self._redact_confirm_frame, text="⬛  Redact All",
            bg=PALETTE["danger"], fg="#0F0F13",
            activebackground="#C05050",
            font=("Helvetica", 9, "bold"), relief="flat", bd=0,
            padx=8, pady=4, cursor="hand2",
            command=self._redact_confirm,
        ).pack(fill=tk.X, pady=(0, 2))

        tk.Button(
            self._redact_confirm_frame, text="✕  Cancel",
            bg=PALETTE["bg_hover"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, relief="flat", bd=0,
            padx=8, pady=3, cursor="hand2",
            command=self._redact_cancel_hits,
        ).pack(fill=tk.X)

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=PALETTE["bg_dark"])
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # ── Inline search/redact bar (hidden by default) ──────────────────
        self._search_bar_frame = tk.Frame(
            frame, bg=PALETTE["bg_mid"], height=40,
            highlightthickness=1, highlightbackground=PALETTE["border"],
        )
        # Not packed yet — shown by _toggle_search_bar()

        def _sb_btn(parent, text, cmd, **kw):
            defaults = dict(
                bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                activebackground=PALETTE["accent_dim"],
                activeforeground=PALETTE["accent_light"],
                font=FONT_LABEL, relief="flat", bd=0,
                padx=8, pady=4, cursor="hand2",
            )
            defaults.update(kw)
            return tk.Button(parent, text=text, command=cmd, **defaults)

        # ✕ close button — far right
        _sb_btn(
            self._search_bar_frame, "✕", self._toggle_search_bar,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            activebackground=PALETTE["bg_hover"],
            font=("Helvetica", 11), padx=10,
        ).pack(side=tk.RIGHT)

        tk.Frame(self._search_bar_frame, bg=PALETTE["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=6)

        # Redact buttons — right side
        self._sb_redact_all_btn = tk.Button(
            self._search_bar_frame,
            text="⬛  Redact All",
            command=self._search_bar_redact_all,
            bg=PALETTE["danger"], fg="#0F0F13",
            activebackground="#C05050",
            font=("Helvetica", 9, "bold"), relief="flat", bd=0,
            padx=10, pady=4, cursor="hand2",
            state=tk.DISABLED,
        )
        self._sb_redact_all_btn.pack(side=tk.RIGHT, padx=(0, 4))

        self._sb_redact_one_btn = tk.Button(
            self._search_bar_frame,
            text="Redact This",
            command=self._search_bar_redact_one,
            bg="#7B2020", fg="#FFCCCC",
            activebackground="#9B3030",
            font=FONT_LABEL, relief="flat", bd=0,
            padx=8, pady=4, cursor="hand2",
            state=tk.DISABLED,
        )
        self._sb_redact_one_btn.pack(side=tk.RIGHT, padx=(0, 4))

        tk.Frame(self._search_bar_frame, bg=PALETTE["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=6)

        # Hit counter label  "3 of 14 (p.2)"
        self._sb_hit_lbl = tk.Label(
            self._search_bar_frame, text="",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            font=FONT_MONO, padx=8, width=18, anchor="w",
        )
        self._sb_hit_lbl.pack(side=tk.RIGHT)

        # Prev / Next navigation arrows
        self._sb_next_btn = _sb_btn(
            self._search_bar_frame, "▶", self._search_bar_next,
            state=tk.DISABLED,
        )
        self._sb_next_btn.pack(side=tk.RIGHT, padx=(0, 2))

        self._sb_prev_btn = _sb_btn(
            self._search_bar_frame, "◀", self._search_bar_prev,
            state=tk.DISABLED,
        )
        self._sb_prev_btn.pack(side=tk.RIGHT, padx=(0, 2))

        tk.Frame(self._search_bar_frame, bg=PALETTE["border"], width=1).pack(
            side=tk.RIGHT, fill=tk.Y, pady=6)

        # Left side: label + entry + case checkbox + Find button
        tk.Label(
            self._search_bar_frame,
            text="🔍  Find & Redact:",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            font=FONT_LABEL, padx=8,
        ).pack(side=tk.LEFT)

        self._sb_query_var = tk.StringVar()
        self._sb_entry = tk.Entry(
            self._search_bar_frame,
            textvariable=self._sb_query_var,
            bg="#252535", fg=PALETTE["fg_primary"],
            insertbackground=PALETTE["fg_primary"],
            relief="flat", highlightthickness=1,
            highlightbackground=PALETTE["border"],
            width=26, font=FONT_UI,
        )
        self._sb_entry.pack(side=tk.LEFT, padx=(0, 6), ipady=4)
        self._sb_entry.bind("<Return>",  lambda e: self._search_bar_find())
        self._sb_entry.bind("<Escape>",  lambda e: self._toggle_search_bar())

        self._sb_case_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self._search_bar_frame,
            text="Aa",
            variable=self._sb_case_var,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_secondary"],
            selectcolor=PALETTE["accent_dim"],
            activebackground=PALETTE["bg_hover"],
            font=FONT_LABEL, cursor="hand2",
        ).pack(side=tk.LEFT, padx=(0, 6))

        _sb_btn(
            self._search_bar_frame, "Search All Pages", self._search_bar_find,
        ).pack(side=tk.LEFT, padx=(0, 4))

        # ── Scrollbars and canvas ─────────────────────────────────────────
        self.v_scroll = ttk.Scrollbar(frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas = tk.Canvas(frame, bg=PALETTE["canvas_bg"],
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set,
                                highlightthickness=0, cursor="crosshair")
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

    # ── sidebar helpers ───────────────────────────────────────────────────────

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                 font=("Helvetica", 8, "bold"), anchor="w", padx=12).pack(fill=tk.X, pady=(12, 2))
        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill=tk.X, padx=12)

    def _opt_lbl(self, parent, text):
        tk.Label(parent, text=text, bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(anchor="w")

    def _sb_mini_btn(self, parent, text, cmd):
        return tk.Button(parent, text=text, command=cmd,
                         bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                         activebackground=PALETTE["accent_dim"],
                         activeforeground=PALETTE["accent_light"],
                         font=FONT_UI, relief="flat", bd=0,
                         padx=10, pady=3, cursor="hand2")

    def _sb_btn(self, parent, text, cmd):
        btn = tk.Button(parent, text=text, command=cmd,
                        bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                        activebackground=PALETTE["bg_hover"],
                        activeforeground=PALETTE["accent_light"],
                        font=FONT_UI, relief="flat", bd=0,
                        padx=12, pady=5, anchor="w", cursor="hand2")
        btn.pack(fill=tk.X, padx=4, pady=1)
        return btn

    # ── search bar (Ctrl+F / top-bar button) ──────────────────────────────────

    def _toggle_search_bar(self):
        """Show or hide the inline search/redact bar above the canvas."""
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
        """Search ALL pages and jump to the first hit."""
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
            self._sb_hit_lbl.config(text=f'No matches')
            self._sb_prev_btn.config(state=tk.DISABLED)
            self._sb_next_btn.config(state=tk.DISABLED)
            self._sb_redact_one_btn.config(state=tk.DISABLED)
            self._sb_redact_all_btn.config(state=tk.DISABLED)
            self._flash_status(f'No matches for "{query}"', color=PALETTE["fg_secondary"])
        # If hits found, _on_search_hit_changed callback updates the UI

    def _search_bar_next(self):
        rt = self._get_tool("redact")
        if rt:
            rt.navigate_next()

    def _search_bar_prev(self):
        rt = self._get_tool("redact")
        if rt:
            rt.navigate_prev()

    def _search_bar_redact_one(self):
        """Redact only the currently focused (yellow) hit."""
        rt = self._get_tool("redact")
        if rt:
            rt.redact_current_hit()
        self._redact_confirm_frame.pack_forget()

    def _search_bar_redact_all(self):
        """Redact every hit across all pages."""
        rt = self._get_tool("redact")
        if rt:
            rt.redact_all_hits()
        self._redact_confirm_frame.pack_forget()

    def _search_bar_clear(self):
        """Clear staged hits without redacting (called when bar is hidden)."""
        rt = self._get_tool("redact")
        if rt and rt.has_search_hits:
            rt.cancel_search()
        self._sb_hit_lbl.config(text="")
        self._sb_prev_btn.config(state=tk.DISABLED)
        self._sb_next_btn.config(state=tk.DISABLED)
        self._sb_redact_one_btn.config(state=tk.DISABLED)
        self._sb_redact_all_btn.config(state=tk.DISABLED)
        self._redact_confirm_frame.pack_forget()

    def _on_search_hit_changed(self, cur_idx: int, total: int):
        """
        Callback fired by RedactTool after every navigation / search update.
        Updates the counter label and enables/disables arrow + redact buttons.
        """
        if total == 0 or cur_idx < 0:
            self._sb_hit_lbl.config(text="No matches", fg=PALETTE["fg_dim"])
            self._sb_prev_btn.config(state=tk.DISABLED)
            self._sb_next_btn.config(state=tk.DISABLED)
            self._sb_redact_one_btn.config(state=tk.DISABLED)
            self._sb_redact_all_btn.config(state=tk.DISABLED)
            return

        rt = self._get_tool("redact")
        page_idx = rt._all_hits[cur_idx][0] if rt else 0
        page_lbl = f"p.{page_idx + 1}"

        self._sb_hit_lbl.config(
            text=f"{cur_idx + 1} of {total}  ({page_lbl})",
            fg=PALETTE["fg_primary"],
        )
        can_nav = total > 1
        self._sb_prev_btn.config(state=tk.NORMAL if can_nav else tk.DISABLED)
        self._sb_next_btn.config(state=tk.NORMAL if can_nav else tk.DISABLED)
        self._sb_redact_one_btn.config(state=tk.NORMAL)
        self._sb_redact_all_btn.config(state=tk.NORMAL)

        # Keep sidebar confirm panel in sync
        self._redact_hit_label.config(text=f"⚠ {total} match(es) across all pages")
        self._redact_confirm_frame.pack(fill=tk.X, pady=(0, 4))

    # ── sidebar events ────────────────────────────────────────────────────────

    def _on_tool_change(self):
        tool_name = self.active_tool.get()
        self._st_tool.config(text=f"Tool: {tool_name.replace('_', ' ').title()}")

        if self._current_tool is not None:
            self._current_tool.deactivate()

        self._txt_opts.pack_forget()
        self._annot_opts.pack_forget()
        self._redact_opts.pack_forget()
        if self.active_tool.get() != "redact":
            rt = self._get_tool("redact")
            if rt and rt.has_pending_hits:
                rt.cancel_hits()

        hints = {
            "text":         ("crosshair", self._txt_opts,
                             "Click canvas to place a text box.\nDrag the grip to move it.\nCtrl+Z to undo after confirming."),
            "insert_image": ("crosshair", None,
                             "Click canvas to choose\nan image file, then drag\nto place it."),
            "highlight":    ("crosshair", self._annot_opts,
                             "Drag to highlight\na region on the page.\nCtrl+Z to undo."),
            "rect_annot":   ("crosshair", self._annot_opts,
                             "Drag to draw a\nrectangle annotation.\nCtrl+Z to undo."),
            "select_text":  ("ibeam",    None,
                             "Click a text block\nor drag to select multiple.\nCtrl+C copies the selection."),
            "extract":      ("arrow",    None,
                             "Click on an image\nto extract it."),
            "redact":       ("crosshair", self._redact_opts,
                             "Drag to permanently redact\na region.\n\nOr use 🔍 Find & Redact\n(Ctrl+F) to search by text.\n\n⚠ Redaction is permanent\nand removes content."),
        }
        cursor, panel, hint_text = hints.get(tool_name, ("crosshair", None, ""))
        self.canvas.config(cursor=cursor)
        if panel:
            panel.pack(fill=tk.X, padx=12, pady=4)
        self._hint.config(text=hint_text, fg=PALETTE["fg_dim"])

        self._current_tool = self._get_tool(tool_name)
        if self._current_tool:
            self._current_tool.activate()

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
                btn.config(bg=PALETTE["accent"], fg="#FFFFFF")
            else:
                btn.config(bg=PALETTE["bg_hover"], fg=PALETTE["fg_secondary"])

    def _pick_global_color(self):
        hex_c = "#{:02x}{:02x}{:02x}".format(*self.text_color)
        result = colorchooser.askcolor(color=hex_c, title="Default Text Color")
        if result and result[0]:
            self.text_color = tuple(int(v) for v in result[0])
            self._color_swatch.config(bg="#{:02x}{:02x}{:02x}".format(*self.text_color))

    # ── annotation option callbacks ───────────────────────────────────────────

    def _pick_annot_stroke_color(self):
        result = colorchooser.askcolor(
            color=self._rgb255_to_hex(self.annot_stroke_rgb),
            title="Annotation Stroke Color",
        )
        if result and result[0]:
            self.annot_stroke_rgb = tuple(int(v) for v in result[0])
            self._annot_stroke_swatch.config(bg=self._rgb255_to_hex(self.annot_stroke_rgb))

    def _on_annot_fill_toggle(self):
        no_fill = self._annot_fill_none_var.get()
        if no_fill:
            self.annot_fill_rgb = None
            self._annot_fill_swatch.config(state=tk.DISABLED)
        else:
            if self.annot_fill_rgb is None:
                self.annot_fill_rgb = (255, 255, 0)
            self._annot_fill_swatch.config(
                bg=self._rgb255_to_hex(self.annot_fill_rgb), state=tk.NORMAL)

    def _pick_annot_fill_color(self):
        current = self._rgb255_to_hex(self.annot_fill_rgb or (255, 255, 0))
        result  = colorchooser.askcolor(color=current, title="Annotation Fill Color")
        if result and result[0]:
            self.annot_fill_rgb = tuple(int(v) for v in result[0])
            self._annot_fill_swatch.config(bg=self._rgb255_to_hex(self.annot_fill_rgb))

    def _on_annot_width_change(self):
        try:
            self.annot_width = max(0.5, min(10.0, float(self._annot_width_var.get())))
        except (ValueError, tk.TclError):
            pass

    # ── redaction option callbacks ────────────────────────────────────────────

    def _pick_redact_fill_color(self):
        r, g, b = [int(v * 255) for v in self.redact_fill_color]
        current  = f"#{r:02x}{g:02x}{b:02x}"
        result   = colorchooser.askcolor(color=current, title="Redaction Fill Color")
        if result and result[0]:
            r8, g8, b8 = [int(v) for v in result[0]]
            self.redact_fill_color = (r8 / 255.0, g8 / 255.0, b8 / 255.0)
            self._redact_fill_swatch.config(bg=f"#{r8:02x}{g8:02x}{b8:02x}")

    def _on_redact_label_change(self):
        self.redact_label = self._redact_label_var.get()

    def _redact_find(self):
        """Search all pages for query text via sidebar panel."""
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
        # hit counter and confirm panel are updated via _on_search_hit_changed callback

    def _redact_confirm(self):
        rt = self._get_tool("redact")
        if rt:
            rt.redact_all_hits()
        self._redact_confirm_frame.pack_forget()
        if self._search_bar_visible:
            self._sb_hit_lbl.config(text="")
            self._sb_redact_one_btn.config(state=tk.DISABLED)
            self._sb_redact_all_btn.config(state=tk.DISABLED)
            self._sb_prev_btn.config(state=tk.DISABLED)
            self._sb_next_btn.config(state=tk.DISABLED)

    def _redact_cancel_hits(self):
        rt = self._get_tool("redact")
        if rt:
            rt.cancel_search()
        self._redact_confirm_frame.pack_forget()
        if self._search_bar_visible:
            self._sb_hit_lbl.config(text="")
            self._sb_redact_one_btn.config(state=tk.DISABLED)
            self._sb_redact_all_btn.config(state=tk.DISABLED)
            self._sb_prev_btn.config(state=tk.DISABLED)
            self._sb_next_btn.config(state=tk.DISABLED)
        self._flash_status("Redaction cancelled", color=PALETTE["fg_secondary"])

    # ── file operations ───────────────────────────────────────────────────────

    def _open_pdf(self):
        if self._unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Unsaved Changes", "You have unsaved changes.\nSave before opening a new file?")
            if answer is None:
                return
            if answer and not self._save_pdf():
                return

        path = filedialog.askopenfilename(
            title="Open PDF", filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")])
        if not path:
            return
        self._open_pdf_path(path)

    def _open_pdf_path(self, path: str):
        """Open a PDF from a known path (used by dialog, recent list, startup screen)."""
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
        try:
            self.doc = PDFDocument(path)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open:\n{ex}")
            # Remove bad path from recent list
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
        """Open a recent file, checking for unsaved changes first."""
        if self._unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Unsaved Changes", "You have unsaved changes.\nSave before opening a recent file?")
            if answer is None:
                return
            if answer and not self._save_pdf():
                return
        self._open_pdf_path(path)

    # ── recent files menu ─────────────────────────────────────────────────────

    def _rebuild_recent_menu(self):
        """Rebuild the ▾ dropdown menu from the current recent list."""
        menu = tk.Menu(
            self._recent_mb, tearoff=0,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            activebackground=PALETTE["accent_dim"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica", 9),
            relief="flat", bd=1,
        )
        recents = self._recent.get()
        if recents:
            for p in recents:
                # Show just the filename, full path in tooltip via label truncation
                label = os.path.basename(p)
                dirname = os.path.dirname(p)
                # Truncate long directory names
                if len(dirname) > 40:
                    dirname = "…" + dirname[-38:]
                menu.add_command(
                    label=f"  {label}\n  {dirname}",
                    command=lambda fp=p: self._open_recent(fp),
                )
            menu.add_separator()
            menu.add_command(
                label="  Clear recent files",
                command=self._clear_recent,
                foreground=PALETTE["fg_dim"],
            )
        else:
            menu.add_command(label="  No recent files", state="disabled")

        self._recent_mb.config(menu=menu)

    def _clear_recent(self):
        self._recent.clear()
        self._rebuild_recent_menu()
        # Refresh startup screen if visible
        if hasattr(self, "_startup_frame") and self._startup_frame:
            self._show_startup_screen()

    # ── startup / welcome screen ──────────────────────────────────────────────

    def _show_startup_screen(self):
        """Draw a welcome screen with recent files over the empty canvas."""
        if self.doc:
            return   # A document is already open — nothing to show

        # Remove any existing startup frame first
        self._hide_startup_screen()

        recents = self._recent.get()

        frame = tk.Frame(
            self.canvas,
            bg=PALETTE["bg_dark"],
        )
        self._startup_frame = frame

        # Centre the content
        inner = tk.Frame(frame, bg=PALETTE["bg_dark"])
        inner.place(relx=0.5, rely=0.5, anchor="center")

        # App logo / title
        tk.Label(
            inner,
            text="◼",
            bg=PALETTE["bg_dark"], fg=PALETTE["accent"],
            font=("Helvetica", 48),
        ).pack(pady=(0, 4))
        tk.Label(
            inner,
            text="PDF Editor",
            bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"],
            font=("Helvetica", 22, "bold"),
        ).pack()
        tk.Label(
            inner,
            text="Open a PDF file to get started",
            bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"],
            font=("Helvetica", 10),
        ).pack(pady=(4, 20))

        # Open button
        tk.Button(
            inner,
            text="📂   Open PDF…",
            command=self._open_pdf,
            bg=PALETTE["accent"], fg="#FFFFFF",
            activebackground=PALETTE["accent_light"],
            activeforeground="#FFFFFF",
            font=("Helvetica", 12, "bold"),
            relief="flat", bd=0,
            padx=28, pady=10,
            cursor="hand2",
        ).pack(pady=(0, 28))

        # Recent files section
        if recents:
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(0, 12))
            tk.Label(
                inner,
                text="RECENT FILES",
                bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"],
                font=("Helvetica", 8, "bold"),
            ).pack(anchor="w", pady=(0, 6))

            for p in recents:
                row = tk.Frame(inner, bg=PALETTE["bg_dark"], cursor="hand2")
                row.pack(fill=tk.X, pady=1)

                name = os.path.basename(p)
                directory = os.path.dirname(p)
                if len(directory) > 48:
                    directory = "…" + directory[-46:]

                name_lbl = tk.Label(
                    row, text=name,
                    bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"],
                    font=("Helvetica", 10), anchor="w", cursor="hand2",
                )
                name_lbl.pack(anchor="w")

                path_lbl = tk.Label(
                    row, text=directory,
                    bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"],
                    font=("Helvetica", 8), anchor="w", cursor="hand2",
                )
                path_lbl.pack(anchor="w")

                # Hover highlight
                def _enter(e, r=row, nl=name_lbl, pl=path_lbl):
                    r.config(bg=PALETTE["bg_hover"])
                    nl.config(bg=PALETTE["bg_hover"], fg=PALETTE["accent_light"])
                    pl.config(bg=PALETTE["bg_hover"])

                def _leave(e, r=row, nl=name_lbl, pl=path_lbl):
                    r.config(bg=PALETTE["bg_dark"])
                    nl.config(bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"])
                    pl.config(bg=PALETTE["bg_dark"])

                def _click(e, fp=p):
                    self._open_pdf_path(fp)

                for widget in (row, name_lbl, path_lbl):
                    widget.bind("<Enter>", _enter)
                    widget.bind("<Leave>", _leave)
                    widget.bind("<Button-1>", _click)

                # Divider between entries
                tk.Frame(inner, bg=PALETTE["border"], height=1).pack(
                    fill=tk.X, pady=(4, 0))

        # Place the frame over the entire canvas
        frame.place(x=0, y=0, relwidth=1, relheight=1)

    def _hide_startup_screen(self):
        """Remove the startup screen if it is showing."""
        if hasattr(self, "_startup_frame") and self._startup_frame:
            try:
                self._startup_frame.destroy()
            except Exception:
                pass
            self._startup_frame = None

    def _save_pdf(self) -> bool:
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

    # ── page management ───────────────────────────────────────────────────────

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
            self._page_label.config(
                text=f"{idx + 1} / {self.doc.page_count}")
            self._st_size.config(
                text=f"{int(page.width)} × {int(page.height)} pt")
        else:
            self._thumb.refresh_all_borders()
            self._render()
        if self._current_tool:
            self._current_tool.activate()

    def _thumb_page_click(self, idx: int):
        if not self.doc or idx == self.current_page_idx:
            return
        self._navigate_to(idx)

    def _thumb_reorder(self, src_idx: int, dst_idx: int):
        """
        Called by ThumbnailPanel after a drag-drop reorder.
        src_idx  — original position of the dragged page.
        dst_idx  — insert-before position in the *original* index space.
        """
        if not self.doc:
            return
        n         = self.doc.page_count
        old_order = list(range(n))

        # Build new order: remove src, insert at dst
        new_order = old_order[:]
        new_order.pop(src_idx)
        insert_at = dst_idx if dst_idx <= src_idx else dst_idx - 1
        new_order.insert(insert_at, src_idx)

        if new_order == old_order:
            return

        cmd = ReorderPagesCommand(self.doc, new_order)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Reorder Error", str(ex))
            return
        self._push_history(cmd)

        # Keep the current page tracking the same logical page
        self.current_page_idx = new_order.index(
            old_order[self.current_page_idx]
        ) if self.current_page_idx < n else 0

        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"↕ Moved page {src_idx + 1} → position {insert_at + 1}")

    def _thumb_add_page(self, after_idx: int):
        """Insert a blank page after after_idx (from thumbnail context menu / + button)."""
        if not self.doc:
            return
        try:
            ref        = self.doc.get_page(max(0, after_idx))
            insert_pos = after_idx + 1
            self.doc.insert_page(insert_pos, width=ref.width, height=ref.height)
        except Exception as ex:
            messagebox.showerror("Add Page Error", str(ex))
            return
        self.current_page_idx = insert_pos
        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"+ Added blank page at position {insert_pos + 1}")

    def _thumb_delete_page(self, idx: int):
        """Delete the page at idx (called from hover badge or context menu)."""
        if not self.doc:
            return
        if self.doc.page_count <= 1:
            messagebox.showwarning("Cannot Delete", "A PDF must have at least one page.")
            return
        if not messagebox.askyesno(
            "Delete Page",
            f"Permanently delete page {idx + 1}?\nThis cannot be undone after saving.",
            icon="warning",
        ):
            return
        try:
            self.doc.delete_page(idx)
        except Exception as ex:
            messagebox.showerror("Delete Error", str(ex))
            return
        self.current_page_idx = min(self.current_page_idx, self.doc.page_count - 1)
        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"✕ Deleted page {idx + 1}")

    def _thumb_duplicate_page(self, idx: int):
        """Duplicate the page at idx, inserting the copy immediately after."""
        if not self.doc:
            return
        cmd = DuplicatePageCommand(self.doc, idx)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Duplicate Error", str(ex))
            return
        self._push_history(cmd)
        self.current_page_idx = idx + 1
        self._mark_dirty()
        self._cont_images.clear()
        self._thumb.reset()
        self._render()
        self._flash_status(f"⧉ Duplicated page {idx + 1}")

    def _thumb_rotate_page(self, idx: int, angle: int):
        """Rotate a specific page by angle (called from context menu)."""
        if not self.doc:
            return
        cmd = RotatePageCommand(self.page_service, self.doc, idx, angle)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Rotate Error", str(ex))
            return
        self._push_history(cmd)
        self._thumb.mark_dirty(idx)
        self._cont_invalidate_cache(idx)
        if idx == self.current_page_idx:
            self._render()
        self._flash_status(
            f"{'↺' if angle < 0 else '↻'} Rotated page {idx + 1} {abs(angle)}°"
        )

    def _rotate(self, angle: int):
        """Rotate current page from sidebar buttons."""
        if not self.doc:
            return
        self._thumb_rotate_page(self.current_page_idx, angle)

    def _add_page(self):
        """Add page from sidebar button — inserts after current page."""
        if not self.doc:
            return
        self._thumb_add_page(self.current_page_idx)

    def _delete_page(self):
        """Delete current page from sidebar button."""
        if not self.doc:
            return
        self._thumb_delete_page(self.current_page_idx)

    # ── zoom ──────────────────────────────────────────────────────────────────

    def _zoom_in(self):
        self._set_zoom(min(MAX_SCALE, self.scale_factor + SCALE_STEP))

    def _zoom_out(self):
        self._set_zoom(max(MIN_SCALE, self.scale_factor - SCALE_STEP))

    def _zoom_reset(self):
        self._set_zoom(RENDER_DPI)

    def _set_zoom(self, s: float):
        self.scale_factor = round(s, 3)
        self._update_zoom_label()
        self._cont_invalidate_cache()   # stale at new scale
        self._render()

    def _update_zoom_label(self):
        pct = int(self.scale_factor / RENDER_DPI * 100)
        self._zoom_label.config(text=f"{pct}%")
        if hasattr(self, "_st_zoom"):
            self._st_zoom.config(text=f"Zoom {pct}%")

    # ── thumbnail panel toggle ────────────────────────────────────────────────

    def _toggle_thumb_panel(self):
        self._thumb_visible = not self._thumb_visible
        if self._thumb_visible:
            self._thumb.show()
            self._thumb_toggle_btn.config(fg=PALETTE["fg_primary"])
        else:
            self._thumb.hide()
            self._thumb_toggle_btn.config(fg=PALETTE["fg_dim"])

    # ── rendering ─────────────────────────────────────────────────────────────

    def _render(self):
        if not self.doc:
            return
        if self._continuous_mode:
            self._render_continuous()
        else:
            self._render_single()

    # ── single-page render ────────────────────────────────────────────────────

    def _render_single(self):
        page = self.doc.get_page(self.current_page_idx)
        ppm  = page.render_to_ppm(scale=self.scale_factor)
        self.tk_image = tk.PhotoImage(data=ppm)

        iw = int(page.width  * self.scale_factor)
        ih = int(page.height * self.scale_factor)

        cw = self.canvas.winfo_width()
        self._page_offset_x = max(40, (cw - iw) // 2)
        self._page_offset_y = 30

        ox, oy = self._page_offset_x, self._page_offset_y
        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")
        self.canvas.delete("page_bg")
        self.canvas.delete("textsel")

        self.canvas.create_rectangle(
            ox + 5, oy + 5, ox + iw + 5, oy + ih + 5,
            fill="#000000", outline="", stipple="gray25", tags="page_shadow")
        self.canvas.create_image(ox, oy, anchor=tk.NW,
                                 image=self.tk_image, tags="page_img")
        self.canvas.config(scrollregion=(0, 0, ox + iw + 50, oy + ih + 50))

        self._page_label.config(text=f"{self.current_page_idx + 1} / {self.doc.page_count}")
        self._st_size.config(text=f"{int(page.width)} × {int(page.height)} pt")

        for box in list(self._text_boxes):
            box.rescale(self.scale_factor, self._page_offset_x, self._page_offset_y)

        self._thumb.refresh_all_borders()
        self._thumb.scroll_to_active()

        if self.active_tool.get() == "select_text":
            sel = self._get_tool("select_text")
            if sel:
                sel.reload()

    # ── continuous scroll render ──────────────────────────────────────────────

    _CONT_GAP = 20   # px gap between pages

    def _cont_page_top(self, idx: int) -> int:
        """Canvas y coordinate of the top of page slot idx in continuous mode."""
        doc = self.doc
        if not doc:
            return 0
        # All pages assumed same height for layout; individual pages may differ.
        # We accumulate actual heights.
        y = self._CONT_GAP
        for i in range(idx):
            p  = doc.get_page(i)
            ih = int(p.height * self.scale_factor)
            y += ih + self._CONT_GAP
        return y

    def _cont_page_at_y(self, canvas_y: float) -> int:
        """Return the page index whose slot contains canvas_y."""
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
        """
        Layout all pages stacked vertically.  Renders the current page
        immediately, then schedules adjacent pages lazily.
        """
        if self._cont_after_id:
            self.root.after_cancel(self._cont_after_id)
            self._cont_after_id = None

        doc = self.doc
        n   = doc.page_count
        cw  = self.canvas.winfo_width()

        # Compute total canvas dimensions
        total_h = self._CONT_GAP
        max_iw  = 0
        heights = []
        widths  = []
        for i in range(n):
            p  = doc.get_page(i)
            iw = int(p.width  * self.scale_factor)
            ih = int(p.height * self.scale_factor)
            heights.append(ih)
            widths.append(iw)
            max_iw   = max(max_iw, iw)
            total_h += ih + self._CONT_GAP

        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")
        self.canvas.delete("page_bg")
        self.canvas.delete("textsel")
        self.canvas.config(scrollregion=(0, 0, max(cw, max_iw + 80), total_h))

        # Draw placeholder backgrounds for all pages first
        y = self._CONT_GAP
        for i in range(n):
            iw, ih = widths[i], heights[i]
            ox = max(40, (cw - iw) // 2)
            self.canvas.create_rectangle(
                ox, y, ox + iw, y + ih,
                fill=PALETTE.get("page_bg", "#FFFFFF"), outline="",
                tags=(f"page_bg", f"page_bg_{i}"),
            )
            self.canvas.create_rectangle(
                ox + 5, y + 5, ox + iw + 5, y + ih + 5,
                fill="#000000", outline="", stipple="gray25",
                tags=(f"page_shadow", f"page_shadow_{i}"),
            )
            # Raise shadow below placeholder
            self.canvas.tag_lower(f"page_shadow_{i}", f"page_bg_{i}")
            y += ih + self._CONT_GAP

        # Update page offset for current page (used by tools)
        self._update_cont_offsets(self.current_page_idx)

        # Render priority order: current page first, then outward
        cur = self.current_page_idx
        order = [cur]
        for delta in range(1, n):
            if cur - delta >= 0:
                order.append(cur - delta)
            if cur + delta < n:
                order.append(cur + delta)

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
        self._page_label.config(
            text=f"{self.current_page_idx + 1} / {n}")
        self._st_size.config(
            text=f"{int(cur_page.width)} × {int(cur_page.height)} pt")

        self._thumb.refresh_all_borders()
        self._thumb.scroll_to_active()

    def _render_cont_page(self, idx: int, iw: int, ih: int, cw: int):
        """Render a single page slot in continuous mode, using cache."""
        doc = self.doc
        if not doc or idx >= doc.page_count:
            return

        cache_key = (idx, self.scale_factor)
        if cache_key not in self._cont_images:
            try:
                page = doc.get_page(idx)
                ppm  = page.render_to_ppm(scale=self.scale_factor)
                self._cont_images[cache_key] = tk.PhotoImage(data=ppm)
            except Exception:
                return

        img = self._cont_images[cache_key]
        y   = self._cont_page_top(idx)
        ox  = max(40, (cw - iw) // 2)

        self.canvas.delete(f"page_img_{idx}")
        self.canvas.create_image(
            ox, y, anchor=tk.NW, image=img,
            tags=("page_img", f"page_img_{idx}"),
        )
        # Keep shadow and placeholder below image
        self.canvas.tag_lower(f"page_bg_{idx}", f"page_img_{idx}")

    def _update_cont_offsets(self, idx: int):
        """Update _page_offset_x/_y to point at page idx in continuous mode."""
        doc = self.doc
        if not doc:
            return
        p   = doc.get_page(idx)
        iw  = int(p.width  * self.scale_factor)
        cw  = self.canvas.winfo_width()
        self._page_offset_x = max(40, (cw - iw) // 2)
        self._page_offset_y = self._cont_page_top(idx)

    def _cont_invalidate_cache(self, page_idx: int | None = None):
        """Clear render cache for one page (or all if None)."""
        if page_idx is None:
            self._cont_images.clear()
        else:
            keys = [k for k in self._cont_images if k[0] == page_idx]
            for k in keys:
                del self._cont_images[k]

    def _on_cont_scroll(self):
        """Called (debounced) after scrolling in continuous mode to update current page."""
        self._scroll_after_id = None
        if not self.doc or not self._continuous_mode:
            return
        # Find which page is most visible in the viewport
        top    = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        mid    = (top + bottom) / 2
        idx    = self._cont_page_at_y(mid)
        if idx != self.current_page_idx:
            self.current_page_idx = idx
            self._update_cont_offsets(idx)
            page = self.doc.get_page(idx)
            self._page_label.config(
                text=f"{idx + 1} / {self.doc.page_count}")
            self._st_size.config(
                text=f"{int(page.width)} × {int(page.height)} pt")
            self._thumb.refresh_all_borders()
            self._thumb.scroll_to_active()

    # ── view mode switching ────────────────────────────────────────────────────

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
        # Scroll to current page after layout
        self.root.after(80, self._scroll_to_current_cont)

    def _update_view_mode_buttons(self):
        """Highlight whichever mode button is active."""
        if not hasattr(self, "_btn_single"):
            return
        if self._continuous_mode:
            self._btn_single.config(
                fg=PALETTE["fg_secondary"],
                bg=PALETTE["bg_mid"],
            )
            self._btn_scroll.config(
                fg=PALETTE["accent_light"],
                bg=PALETTE["bg_hover"],
            )
        else:
            self._btn_single.config(
                fg=PALETTE["accent_light"],
                bg=PALETTE["bg_hover"],
            )
            self._btn_scroll.config(
                fg=PALETTE["fg_secondary"],
                bg=PALETTE["bg_mid"],
            )

    def _scroll_to_current_cont(self):
        """In continuous mode, scroll canvas so current page is in view."""
        if not self.doc:
            return
        y_top    = self._cont_page_top(self.current_page_idx)
        total_h  = self._cont_page_top(self.doc.page_count)  # past-end y
        if total_h > 0:
            frac = max(0.0, (y_top - self._CONT_GAP) / total_h)
            self.canvas.yview_moveto(frac)

    # ── canvas events ─────────────────────────────────────────────────────────

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        if self._continuous_mode:
            # Determine which page was clicked and update current page
            idx = self._cont_page_at_y(cy)
            if idx != self.current_page_idx:
                self.current_page_idx = idx
                self._update_cont_offsets(idx)
                self._thumb.refresh_all_borders()
                self._thumb.scroll_to_active()
                page = self.doc.get_page(idx)
                self._page_label.config(
                    text=f"{idx + 1} / {self.doc.page_count}")
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

        # In continuous mode, debounce a check for which page is now in view
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

    # ── text box lifecycle ────────────────────────────────────────────────────

    def _spawn_textbox(self, pdf_x: float, pdf_y: float):
        page  = self.doc.get_page(self.current_page_idx)
        pdf_w = page.width * 0.42
        pdf_h = self.fontsize * 4

        bg_color = self._sample_page_color(pdf_x, pdf_y)

        box = TextBox(
            canvas=self.canvas,
            pdf_x=pdf_x, pdf_y=pdf_y,
            pdf_w=pdf_w, pdf_h=pdf_h,
            scale=self.scale_factor,
            page_offset_x=self._page_offset_x,
            page_offset_y=self._page_offset_y,
            font_index=self.font_index,
            fontsize=self.fontsize,
            color_rgb=self.text_color,
            entry_bg=bg_color,
            align=self.text_align,
            on_commit=self._on_box_confirmed,
            on_delete=self._on_box_deleted,
            on_interact=self._on_box_interact,
        )
        self._text_boxes.append(box)

    def _sample_page_color(self, pdf_x: float, pdf_y: float) -> str:
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

    # ── history ───────────────────────────────────────────────────────────────

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

    # ── status helpers ────────────────────────────────────────────────────────

    def _flash_status(self, message: str, color: str = None, duration_ms: int = 3000):
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
            self.root.title(f"PDF Editor — {name}{marker}")
        else:
            self.root.title("PDF Editor — Untitled •" if self._unsaved_changes
                            else "PDF Editor")

    def _mark_dirty(self):
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    # ── escape key ────────────────────────────────────────────────────────────

    def _on_escape(self):
        """Escape: close search bar if open, otherwise dismiss text boxes."""
        if self._search_bar_visible:
            self._toggle_search_bar()
        else:
            self._dismiss_boxes()

    # ── colour helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _rgb255_to_hex(rgb: tuple) -> str:
        r, g, b = [max(0, min(255, int(v))) for v in rgb]
        return f"#{r:02x}{g:02x}{b:02x}"

    # ── closing ───────────────────────────────────────────────────────────────

    def _on_closing(self):
        if self._unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Unsaved Changes", "You have unsaved changes.\nSave before closing?")
            if answer is None:
                return
            if answer and not self._save_pdf():
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