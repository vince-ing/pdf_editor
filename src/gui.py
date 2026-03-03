"""
PDF Editor — Modern GUI
A polished, production-grade tkinter PDF editor with:
  • Draggable, editable, resizable text overlays
  • Consistent page rendering at locked DPI
  • Smooth zoom in/out with Ctrl+scroll
  • Dark sidebar + canvas + status bar aesthetic
  • Command-pattern architecture for future undo/redo
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import os
import io

from src.core.document import PDFDocument
from src.services.page_service import PageService
from src.services.image_service import ImageService
from src.services.text_service import TextService
from src.commands.insert_text import InsertTextCommand
from src.commands.rotate_page import RotatePageCommand
from src.commands.extract_images import ExtractSingleImageCommand


# ── Design tokens ─────────────────────────────────────────────────────────────
PALETTE = dict(
    bg_dark      = "#0F0F13",
    bg_mid       = "#16161D",
    bg_panel     = "#1C1C26",
    bg_hover     = "#252535",
    border       = "#2A2A3D",
    accent       = "#7B61FF",
    accent_light = "#A594FF",
    accent_dim   = "#3D2F9E",
    success      = "#34D399",
    danger       = "#F87171",
    warn         = "#FBBF24",
    fg_primary   = "#E8E8F0",
    fg_secondary = "#8888AA",
    fg_dim       = "#505068",
    canvas_bg    = "#252535",
    shadow       = "#09090F",
)

FONT_MONO   = ("JetBrains Mono", 9)
FONT_UI     = ("SF Pro Display", 10)
FONT_LABEL  = ("SF Pro Display", 8)
FONT_TITLE  = ("SF Pro Display", 12, "bold")

PDF_FONTS = ["helv", "tiro", "cour", "zadb", "symb"]
PDF_FONT_LABELS = ["Helvetica", "Times New Roman", "Courier", "Zapf Dingbats", "Symbol"]

RENDER_DPI    = 1.5   # base scale factor (96 dpi equivalent)
MIN_SCALE     = 0.4
MAX_SCALE     = 4.0
SCALE_STEP    = 0.15

HANDLE_SIZE   = 8     # resize handle px
MIN_BOX_W     = 60
MIN_BOX_H     = 28


# ══════════════════════════════════════════════════════════════════════════════
#  TextBox — self-contained, draggable, resizable overlay
# ══════════════════════════════════════════════════════════════════════════════

class TextBox:
    """
    A draggable, resizable, editable text overlay on the PDF canvas.

    The box holds its position in *PDF space* (pdf_x, pdf_y, pdf_w, pdf_h)
    and redraws itself in canvas space whenever the scale changes.

    Lifecycle:
        • Created when user clicks in text-tool mode.
        • Confirmed  → calls on_commit(box)
        • Deleted    → calls on_delete(box) and destroys itself
    """

    # Visual constants
    BORDER_NORMAL   = "#7B61FF"
    BORDER_ACTIVE   = "#A594FF"
    BORDER_HOVER    = "#5B47CC"
    FILL_BG         = "#FFFFFF"
    FILL_TEXT       = "#111111"
    TOOLBAR_BG      = "#1C1C26"
    TOOLBAR_FG      = "#E8E8F0"

    def __init__(
        self,
        canvas: tk.Canvas,
        pdf_x: float, pdf_y: float,
        pdf_w: float, pdf_h: float,
        scale: float,
        font_index: int = 0,
        fontsize: int   = 14,
        color_rgb: tuple = (0, 0, 0),
        text: str = "",
        on_commit = None,
        on_delete = None,
    ):
        self.canvas    = canvas
        self.pdf_x     = pdf_x
        self.pdf_y     = pdf_y
        self.pdf_w     = pdf_w
        self.pdf_h     = pdf_h
        self.scale     = scale
        self.font_index = font_index
        self.fontsize   = fontsize
        self.color_rgb  = color_rgb   # (r, g, b) 0–255
        self.on_commit  = on_commit
        self.on_delete  = on_delete
        self.committed  = False

        # Canvas item IDs
        self._ids: list = []
        self._border_id = None
        self._handles: dict = {}   # key → canvas_id
        self._entry_win_id = None
        self._toolbar_win_id = None

        # Drag state
        self._drag_mode: str | None = None   # "move" | "resize_se"
        self._drag_start = None

        # Widgets (created once, repositioned on resize)
        self._toolbar_frame = None
        self._entry        = None
        self._entry_var    = tk.StringVar(value=text)
        self._font_var     = tk.StringVar(value=PDF_FONT_LABELS[font_index])
        self._size_var     = tk.IntVar(value=fontsize)

        self._build()

    # ──────────────────────────── Build ───────────────────────────────────────

    def _build(self):
        c = self.canvas
        cx, cy, cw, ch = self._canvas_geom()

        # ── Border rectangle ──────────────────────────────────────────────────
        self._border_id = c.create_rectangle(
            cx, cy, cx + cw, cy + ch,
            outline=self.BORDER_ACTIVE, width=2, dash=(6, 3),
            tags="textbox_border",
        )
        self._ids.append(self._border_id)

        # ── Resize handles ────────────────────────────────────────────────────
        for key in ("se",):
            hid = c.create_rectangle(0, 0, 1, 1,
                fill=self.BORDER_ACTIVE, outline="", tags="textbox_handle")
            self._handles[key] = hid
            self._ids.append(hid)
            c.tag_bind(hid, "<ButtonPress-1>",   lambda e, k=key: self._on_handle_press(e, k))
            c.tag_bind(hid, "<B1-Motion>",       self._on_handle_drag)
            c.tag_bind(hid, "<ButtonRelease-1>", self._on_handle_release)
            c.tag_bind(hid, "<Enter>", lambda e: c.config(cursor="size_nw_se"))
            c.tag_bind(hid, "<Leave>", lambda e: c.config(cursor="crosshair"))

        # ── Toolbar (embedded frame) ──────────────────────────────────────────
        self._toolbar_frame = tk.Frame(c, bg=self.TOOLBAR_BG, padx=5, pady=3)

        # Font family
        font_combo = ttk.Combobox(
            self._toolbar_frame, textvariable=self._font_var,
            values=PDF_FONT_LABELS, state="readonly", width=13,
        )
        font_combo.pack(side=tk.LEFT, padx=(0, 4))
        font_combo.bind("<<ComboboxSelected>>", self._on_font_change)

        # Font size
        size_spin = tk.Spinbox(
            self._toolbar_frame, from_=6, to=144,
            textvariable=self._size_var, width=4,
            command=self._on_size_change,
            bg="#252535", fg=self.TOOLBAR_FG,
            buttonbackground="#2A2A3D", relief="flat", highlightthickness=0,
        )
        size_spin.pack(side=tk.LEFT, padx=(0, 4))
        size_spin.bind("<Return>", lambda e: self._on_size_change())

        # Color swatch
        self._color_btn = tk.Button(
            self._toolbar_frame, text="  ", relief="flat", bd=0,
            bg=self._rgb_to_hex(self.color_rgb), width=2,
            cursor="hand2", command=self._pick_color,
        )
        self._color_btn.pack(side=tk.LEFT, padx=(0, 8))

        # Confirm
        tk.Button(
            self._toolbar_frame, text="✓", bg=PALETTE["success"],
            fg="#0F0F13", font=("Helvetica", 10, "bold"), relief="flat",
            bd=0, padx=7, cursor="hand2", command=self._confirm,
        ).pack(side=tk.LEFT, padx=(0, 3))

        # Delete
        tk.Button(
            self._toolbar_frame, text="✕", bg=PALETTE["danger"],
            fg="#0F0F13", font=("Helvetica", 10, "bold"), relief="flat",
            bd=0, padx=7, cursor="hand2", command=self._delete,
        ).pack(side=tk.LEFT)

        self._toolbar_win_id = c.create_window(cx, cy - 34, anchor=tk.NW,
                                                window=self._toolbar_frame)
        self._ids.append(self._toolbar_win_id)

        # ── Text entry ────────────────────────────────────────────────────────
        self._entry = tk.Text(
            c, relief="flat", bd=2,
            bg=self.FILL_BG, fg=self.FILL_TEXT,
            font=self._tk_font(),
            insertbackground=self.BORDER_ACTIVE,
            highlightthickness=1,
            highlightcolor=self.BORDER_ACTIVE,
            highlightbackground=self.BORDER_ACTIVE,
            wrap=tk.WORD, undo=True,
        )
        if self._entry_var.get():
            self._entry.insert("1.0", self._entry_var.get())

        self._entry_win_id = c.create_window(
            cx + 2, cy + 2, anchor=tk.NW,
            window=self._entry,
            width=max(MIN_BOX_W, cw - 4),
            height=max(MIN_BOX_H, ch - 4),
        )
        self._ids.append(self._entry_win_id)

        # ── Drag bindings on entry ────────────────────────────────────────────
        self._entry.bind("<ButtonPress-1>",   self._on_entry_press)
        self._entry.bind("<B1-Motion>",       self._on_entry_drag)
        self._entry.bind("<ButtonRelease-1>", self._on_entry_release)
        self._entry.bind("<Control-Return>",  lambda e: self._confirm())
        self._entry.bind("<Escape>",          lambda e: self._delete())

        # Drag on border
        c.tag_bind(self._border_id, "<ButtonPress-1>",   self._on_border_press)
        c.tag_bind(self._border_id, "<B1-Motion>",       self._on_border_drag)
        c.tag_bind(self._border_id, "<ButtonRelease-1>", self._on_border_release)
        c.tag_bind(self._border_id, "<Enter>",
                   lambda e: c.itemconfig(self._border_id, outline=self.BORDER_HOVER))
        c.tag_bind(self._border_id, "<Leave>",
                   lambda e: c.itemconfig(self._border_id, outline=self.BORDER_ACTIVE))

        self._place_handles(cx, cy, cw, ch)
        self._entry.focus_set()

    # ──────────────────────────── Geometry ────────────────────────────────────

    def _canvas_geom(self):
        """Returns (canvas_x, canvas_y, canvas_w, canvas_h)."""
        return (
            self.pdf_x * self.scale,
            self.pdf_y * self.scale,
            self.pdf_w * self.scale,
            self.pdf_h * self.scale,
        )

    def _place_handles(self, cx, cy, cw, ch):
        hs = HANDLE_SIZE
        positions = {"se": (cx + cw - hs // 2, cy + ch - hs // 2)}
        for key, (hx, hy) in positions.items():
            hid = self._handles[key]
            self.canvas.coords(hid, hx, hy, hx + hs, hy + hs)

    def rescale(self, new_scale: float):
        """Reposition all canvas items when zoom changes."""
        self.scale = new_scale
        cx, cy, cw, ch = self._canvas_geom()
        self.canvas.coords(self._border_id, cx, cy, cx + cw, cy + ch)
        self.canvas.coords(self._toolbar_win_id, cx, cy - 34)
        self.canvas.coords(self._entry_win_id, cx + 2, cy + 2)
        self.canvas.itemconfigure(self._entry_win_id,
                                  width=max(MIN_BOX_W, cw - 4),
                                  height=max(MIN_BOX_H, ch - 4))
        self._place_handles(cx, cy, cw, ch)

    # ──────────────────────────── Drag: move ──────────────────────────────────

    def _on_border_press(self, event):
        self._drag_mode  = "move"
        self._drag_start = (event.x_root, event.y_root)

    def _on_border_drag(self, event):
        if self._drag_mode != "move" or not self._drag_start:
            return
        dx = (event.x_root - self._drag_start[0]) / self.scale
        dy = (event.y_root - self._drag_start[1]) / self.scale
        self._drag_start = (event.x_root, event.y_root)
        self.pdf_x += dx
        self.pdf_y += dy
        self.rescale(self.scale)

    def _on_border_release(self, _event):
        self._drag_mode  = None
        self._drag_start = None

    # Allow dragging from text entry only when Ctrl is held (else normal text selection)
    def _on_entry_press(self, event):
        if event.state & 0x0004:   # Ctrl key
            self._drag_mode  = "move"
            self._drag_start = (event.x_root, event.y_root)

    def _on_entry_drag(self, event):
        if self._drag_mode == "move" and self._drag_start:
            dx = (event.x_root - self._drag_start[0]) / self.scale
            dy = (event.y_root - self._drag_start[1]) / self.scale
            self._drag_start = (event.x_root, event.y_root)
            self.pdf_x += dx
            self.pdf_y += dy
            self.rescale(self.scale)
            return "break"

    def _on_entry_release(self, _event):
        self._drag_mode  = None
        self._drag_start = None

    # ──────────────────────────── Drag: resize ────────────────────────────────

    def _on_handle_press(self, event, key: str):
        self._drag_mode  = f"resize_{key}"
        self._drag_start = (event.x_root, event.y_root)

    def _on_handle_drag(self, event):
        if not self._drag_start or "resize" not in (self._drag_mode or ""):
            return
        dx = (event.x_root - self._drag_start[0]) / self.scale
        dy = (event.y_root - self._drag_start[1]) / self.scale
        self._drag_start = (event.x_root, event.y_root)
        if "se" in self._drag_mode:
            self.pdf_w = max(MIN_BOX_W / self.scale, self.pdf_w + dx)
            self.pdf_h = max(MIN_BOX_H / self.scale, self.pdf_h + dy)
        self.rescale(self.scale)

    def _on_handle_release(self, _event):
        self._drag_mode  = None
        self._drag_start = None

    # ──────────────────────────── Options ─────────────────────────────────────

    def _on_font_change(self, _event=None):
        self.font_index = PDF_FONT_LABELS.index(self._font_var.get())
        self._entry.config(font=self._tk_font())

    def _on_size_change(self, _event=None):
        try:
            self.fontsize = max(6, min(144, int(self._size_var.get())))
        except (ValueError, tk.TclError):
            pass
        self._entry.config(font=self._tk_font())

    def _pick_color(self):
        hex_start = self._rgb_to_hex(self.color_rgb)
        result = colorchooser.askcolor(color=hex_start, title="Text Color")
        if result and result[0]:
            r, g, b = [int(v) for v in result[0]]
            self.color_rgb = (r, g, b)
            self._color_btn.config(bg=self._rgb_to_hex(self.color_rgb))
            self._entry.config(fg=self._rgb_to_hex(self.color_rgb))

    # ──────────────────────────── Confirm / Delete ────────────────────────────

    def get_text(self) -> str:
        try:
            return self._entry.get("1.0", tk.END).rstrip("\n")
        except Exception:
            return ""

    def _confirm(self):
        text = self.get_text().strip()
        if not text:
            self._delete()
            return
        self.committed = True
        if self.on_commit:
            self.on_commit(self)
        self.destroy()

    def _delete(self):
        if self.on_delete:
            self.on_delete(self)
        self.destroy()

    def destroy(self):
        for item_id in self._ids:
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass
        for w in (self._toolbar_frame, self._entry):
            try:
                if w and w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
        self._ids.clear()
        self._handles.clear()

    # ──────────────────────────── Helpers ─────────────────────────────────────

    def _tk_font(self) -> tuple:
        label = PDF_FONT_LABELS[self.font_index]
        family_map = {
            "Helvetica":       "Helvetica",
            "Times New Roman": "Times New Roman",
            "Courier":         "Courier New",
            "Zapf Dingbats":   "Helvetica",
            "Symbol":          "Helvetica",
        }
        return (family_map.get(label, "Helvetica"), self.fontsize)

    @staticmethod
    def _rgb_to_hex(rgb: tuple) -> str:
        r, g, b = [max(0, min(255, int(v))) for v in rgb]
        return f"#{r:02x}{g:02x}{b:02x}"

    @property
    def pdf_font_name(self) -> str:
        return PDF_FONTS[self.font_index]

    @property
    def pdf_color(self) -> tuple:
        """Returns color as 0.0–1.0 float tuple for PyMuPDF."""
        return tuple(v / 255.0 for v in self.color_rgb)


# ══════════════════════════════════════════════════════════════════════════════
#  Tooltip helper
# ══════════════════════════════════════════════════════════════════════════════

class Tooltip:
    def __init__(self, widget, text: str):
        self._tip = None
        widget.bind("<Enter>", lambda e: self._show(e, text))
        widget.bind("<Leave>", self._hide)

    def _show(self, event, text):
        x = event.widget.winfo_rootx() + 20
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel()
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        lbl = tk.Label(tw, text=text, bg="#1C1C26", fg="#E8E8F0",
                       font=("Helvetica", 9), relief="flat", padx=8, pady=4,
                       bd=1, highlightbackground="#2A2A3D", highlightthickness=1)
        lbl.pack()

    def _hide(self, _event=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None


# ══════════════════════════════════════════════════════════════════════════════
#  Main Application
# ══════════════════════════════════════════════════════════════════════════════

class InteractivePDFEditor:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF Editor")
        self.root.geometry("1200x820")
        self.root.minsize(800, 600)
        self.root.configure(bg=PALETTE["bg_dark"])

        # ── Document state ────────────────────────────────────────────────────
        self.doc: PDFDocument | None = None
        self.current_page_idx = 0
        self.scale_factor     = RENDER_DPI
        self.tk_image         = None
        self._page_offset_x   = 0   # canvas centering offset
        self._page_offset_y   = 20

        # ── Services ──────────────────────────────────────────────────────────
        self.page_service  = PageService()
        self.text_service  = TextService()
        self.image_service = ImageService()

        # ── Tool state ────────────────────────────────────────────────────────
        self.active_tool   = tk.StringVar(value="text")
        self.font_index    = 0
        self.fontsize      = 14
        self.text_color    = (0, 0, 0)   # (r, g, b) 0–255

        # ── Active text boxes ─────────────────────────────────────────────────
        self._text_boxes: list[TextBox] = []

        # ── History (simple linear) ───────────────────────────────────────────
        self._history: list = []       # list of Command objects
        self._history_idx: int = -1

        self._build_ui()
        self._apply_ttk_style()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ─────────────────────────── ttk Styling ──────────────────────────────────

    def _apply_ttk_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TCombobox",
                         fieldbackground="#252535",
                         background="#252535",
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

        style.configure("Vertical.TScrollbar",
                         background=PALETTE["bg_panel"],
                         troughcolor=PALETTE["bg_dark"],
                         bordercolor=PALETTE["border"],
                         arrowcolor=PALETTE["fg_dim"])
        style.configure("Horizontal.TScrollbar",
                         background=PALETTE["bg_panel"],
                         troughcolor=PALETTE["bg_dark"],
                         bordercolor=PALETTE["border"],
                         arrowcolor=PALETTE["fg_dim"])

    # ─────────────────────────────── UI Build ─────────────────────────────────

    def _build_ui(self):
        self._build_topbar()

        body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        body.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(body)
        self._build_canvas_area(body)
        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["bg_mid"], height=44)
        bar.pack(fill=tk.X, side=tk.TOP)
        bar.pack_propagate(False)

        # Logo / title
        tk.Label(bar, text="◼ PDF Editor", bg=PALETTE["bg_mid"],
                 fg=PALETTE["accent_light"],
                 font=("Helvetica", 13, "bold"), padx=16).pack(side=tk.LEFT)

        sep = tk.Frame(bar, bg=PALETTE["border"], width=1)
        sep.pack(side=tk.LEFT, fill=tk.Y, pady=8)

        # Top-level actions
        topbar_actions = [
            ("📂  Open",    self._open_pdf,   "Open a PDF file  (Ctrl+O)"),
            ("💾  Save",    self._save_pdf,   "Save PDF  (Ctrl+S)"),
            ("↩  Undo",    self._undo,        "Undo last action  (Ctrl+Z)"),
        ]
        for label, cmd, tip in topbar_actions:
            btn = self._topbar_btn(bar, label, cmd)
            Tooltip(btn, tip)

        sep2 = tk.Frame(bar, bg=PALETTE["border"], width=1)
        sep2.pack(side=tk.LEFT, fill=tk.Y, pady=8)

        # Zoom controls
        tk.Label(bar, text="Zoom:", bg=PALETTE["bg_mid"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL, padx=8).pack(side=tk.LEFT)
        self._zoom_label = tk.Label(bar, text=f"{int(self.scale_factor / RENDER_DPI * 100)}%",
                                    bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
                                    font=FONT_MONO, width=5)
        self._zoom_label.pack(side=tk.LEFT)
        btn_zm = self._topbar_btn(bar, "−", self._zoom_out)
        Tooltip(btn_zm, "Zoom out  (Ctrl+−)")
        btn_zp = self._topbar_btn(bar, "+", self._zoom_in)
        Tooltip(btn_zp, "Zoom in  (Ctrl+=)")
        btn_zr = self._topbar_btn(bar, "⟳", self._zoom_reset)
        Tooltip(btn_zr, "Reset zoom  (Ctrl+0)")

        # Keyboard bindings
        self.root.bind("<Control-o>", lambda e: self._open_pdf())
        self.root.bind("<Control-s>", lambda e: self._save_pdf())
        self.root.bind("<Control-z>", lambda e: self._undo())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>",     lambda e: self._zoom_reset())
        self.root.bind("<Left>",  lambda e: self._prev_page())
        self.root.bind("<Right>", lambda e: self._next_page())
        self.root.bind("<Escape>", lambda e: self._dismiss_active_boxes())

    def _topbar_btn(self, parent, text: str, command) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command,
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            activebackground=PALETTE["bg_hover"], activeforeground=PALETTE["accent_light"],
            font=("Helvetica", 10), relief="flat", bd=0,
            padx=12, pady=0, cursor="hand2", highlightthickness=0,
        )
        btn.pack(side=tk.LEFT, fill=tk.Y)
        return btn

    def _build_sidebar(self, parent):
        self._sidebar = tk.Frame(parent, bg=PALETTE["bg_panel"], width=200)
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar.pack_propagate(False)

        self._section_label(self._sidebar, "NAVIGATION")

        nav = tk.Frame(self._sidebar, bg=PALETTE["bg_panel"])
        nav.pack(fill=tk.X, padx=12, pady=6)
        self._sb_btn(nav, "◀", self._prev_page).pack(side=tk.LEFT)
        self._page_label = tk.Label(nav, text="—", bg=PALETTE["bg_panel"],
                                    fg=PALETTE["fg_primary"], font=FONT_UI)
        self._page_label.pack(side=tk.LEFT, expand=True)
        self._sb_btn(nav, "▶", self._next_page).pack(side=tk.RIGHT)

        self._section_label(self._sidebar, "PAGE ACTIONS")
        self._sidebar_btn(self._sidebar, "↺  Rotate Left",  lambda: self._rotate(-90))
        self._sidebar_btn(self._sidebar, "↻  Rotate Right", lambda: self._rotate(90))
        self._sidebar_btn(self._sidebar, "+ Add Page",       self._add_page)
        self._sidebar_btn(self._sidebar, "✕ Delete Page",   self._delete_page)

        self._section_label(self._sidebar, "ACTIVE TOOL")

        for label, value, tip in [
            ("📝  Text",         "text",    "Click canvas to add text"),
            ("🖼  Extract Image","extract", "Click an image to extract"),
        ]:
            rb = tk.Radiobutton(
                self._sidebar, text=label,
                variable=self.active_tool, value=value,
                bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                selectcolor=PALETTE["accent_dim"],
                activebackground=PALETTE["bg_hover"],
                activeforeground=PALETTE["accent_light"],
                font=("Helvetica", 10), anchor="w",
                cursor="hand2", command=self._on_tool_change,
            )
            rb.pack(fill=tk.X, padx=12, pady=2)
            Tooltip(rb, tip)

        # ── Text options ───────────────────────────────────────────────────────
        self._section_label(self._sidebar, "TEXT OPTIONS")
        self._text_opts = tk.Frame(self._sidebar, bg=PALETTE["bg_panel"])
        self._text_opts.pack(fill=tk.X, padx=12, pady=4)

        self._opt_label(self._text_opts, "Font Family")
        self._sb_font_var = tk.StringVar(value=PDF_FONT_LABELS[self.font_index])
        font_combo = ttk.Combobox(self._text_opts, textvariable=self._sb_font_var,
                                  values=PDF_FONT_LABELS, state="readonly", width=18)
        font_combo.pack(fill=tk.X, pady=(0, 8))
        font_combo.bind("<<ComboboxSelected>>", self._sb_font_change)

        self._opt_label(self._text_opts, "Font Size")
        self._sb_size_var = tk.IntVar(value=self.fontsize)
        size_row = tk.Frame(self._text_opts, bg=PALETTE["bg_panel"])
        size_row.pack(fill=tk.X, pady=(0, 8))
        tk.Spinbox(
            size_row, from_=6, to=144, textvariable=self._sb_size_var, width=6,
            command=self._sb_size_change,
            bg="#252535", fg=PALETTE["fg_primary"],
            buttonbackground=PALETTE["border"], relief="flat", highlightthickness=0,
        ).pack(side=tk.LEFT)

        self._opt_label(self._text_opts, "Text Color")
        color_row = tk.Frame(self._text_opts, bg=PALETTE["bg_panel"])
        color_row.pack(fill=tk.X, pady=(0, 4))
        self._color_swatch = tk.Button(
            color_row, bg="#000000", width=3, relief="flat", bd=2,
            cursor="hand2", command=self._pick_global_color,
        )
        self._color_swatch.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(color_row, text="Pick color", bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(side=tk.LEFT)

        # ── Hint ──────────────────────────────────────────────────────────────
        self._hint = tk.Label(
            self._sidebar,
            text="Click canvas to place\na text box.\nCtrl+drag to move it.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=FONT_LABEL, justify="center", wraplength=176,
        )
        self._hint.pack(side=tk.BOTTOM, pady=16)

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=PALETTE["bg_dark"])
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

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

        self.canvas.bind("<Button-1>",    self._on_canvas_click)
        self.canvas.bind("<MouseWheel>",  self._on_mousewheel)
        self.canvas.bind("<Button-4>",    self._on_mousewheel)
        self.canvas.bind("<Button-5>",    self._on_mousewheel)
        self.canvas.bind("<Motion>",      self._on_mouse_motion)
        self.canvas.bind("<Control-MouseWheel>",   self._on_ctrl_scroll)
        self.canvas.bind("<Control-Button-4>",     self._on_ctrl_scroll)
        self.canvas.bind("<Control-Button-5>",     self._on_ctrl_scroll)
        self.canvas.bind("<Configure>",   self._on_canvas_resize)

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["shadow"], height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        def _sep():
            tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
                side=tk.LEFT, fill=tk.Y, pady=4)

        self._st_tool = tk.Label(bar, text="Tool: Text", bg=PALETTE["shadow"],
                                 fg=PALETTE["fg_dim"], font=FONT_MONO, padx=10)
        self._st_tool.pack(side=tk.LEFT)
        _sep()

        self._st_coords = tk.Label(bar, text="x: —   y: —", bg=PALETTE["shadow"],
                                   fg=PALETTE["fg_dim"], font=FONT_MONO, padx=10)
        self._st_coords.pack(side=tk.LEFT)
        _sep()

        self._st_page_size = tk.Label(bar, text="", bg=PALETTE["shadow"],
                                      fg=PALETTE["fg_dim"], font=FONT_MONO, padx=10)
        self._st_page_size.pack(side=tk.LEFT)

        self._st_zoom = tk.Label(bar, text=f"Zoom {int(self.scale_factor / RENDER_DPI * 100)}%",
                                 bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
                                 font=FONT_MONO, padx=10)
        self._st_zoom.pack(side=tk.RIGHT)

    # ─────────────────────────── Sidebar helpers ───────────────────────────────

    def _section_label(self, parent, title: str):
        tk.Label(parent, text=title, bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_dim"], font=("Helvetica", 8, "bold"),
                 anchor="w", padx=12).pack(fill=tk.X, pady=(12, 2))
        tk.Frame(parent, bg=PALETTE["border"], height=1).pack(fill=tk.X, padx=12)

    def _opt_label(self, parent, text: str):
        tk.Label(parent, text=text, bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(anchor="w")

    def _sb_btn(self, parent, text: str, cmd) -> tk.Button:
        return tk.Button(parent, text=text, command=cmd,
                         bg=PALETTE["bg_hover"], fg=PALETTE["fg_primary"],
                         activebackground=PALETTE["accent_dim"],
                         activeforeground=PALETTE["accent_light"],
                         font=("Helvetica", 10), relief="flat", bd=0,
                         padx=10, pady=3, cursor="hand2")

    def _sidebar_btn(self, parent, text: str, cmd) -> tk.Button:
        btn = tk.Button(parent, text=text, command=cmd,
                        bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                        activebackground=PALETTE["bg_hover"],
                        activeforeground=PALETTE["accent_light"],
                        font=("Helvetica", 10), relief="flat", bd=0,
                        padx=12, pady=5, anchor="w", cursor="hand2")
        btn.pack(fill=tk.X, padx=4, pady=1)
        return btn

    # ─────────────────────────── Sidebar events ────────────────────────────────

    def _on_tool_change(self):
        tool = self.active_tool.get()
        self._st_tool.config(text=f"Tool: {tool.title()}")
        if tool == "text":
            self._hint.config(text="Click canvas to place\na text box.\nCtrl+drag to move it.")
            self.canvas.config(cursor="crosshair")
            self._text_opts.pack(fill=tk.X, padx=12, pady=4)
        else:
            self._hint.config(text="Click on an image\nto extract it.")
            self.canvas.config(cursor="arrow")
            self._text_opts.pack_forget()

    def _sb_font_change(self, _=None):
        self.font_index = PDF_FONT_LABELS.index(self._sb_font_var.get())

    def _sb_size_change(self, _=None):
        try:
            self.fontsize = max(6, min(144, int(self._sb_size_var.get())))
        except (ValueError, tk.TclError):
            pass

    def _pick_global_color(self):
        hex_start = "#{:02x}{:02x}{:02x}".format(*self.text_color)
        result = colorchooser.askcolor(color=hex_start, title="Default Text Color")
        if result and result[0]:
            self.text_color = tuple(int(v) for v in result[0])
            self._color_swatch.config(bg="#{:02x}{:02x}{:02x}".format(*self.text_color))

    # ─────────────────────────── File operations ───────────────────────────────

    def _open_pdf(self):
        path = filedialog.askopenfilename(
            title="Open PDF", filetypes=[("PDF Files", "*.pdf"), ("All files", "*.*")])
        if not path:
            return
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
        try:
            self.doc = PDFDocument(path)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open PDF:\n{ex}")
            return
        self.current_page_idx = 0
        self._history.clear()
        self._history_idx = -1
        self.root.title(f"PDF Editor — {os.path.basename(path)}")
        self._render()

    def _save_pdf(self):
        if not self.doc:
            return
        self._commit_all_boxes()
        path = filedialog.asksaveasfilename(
            title="Save PDF As",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")])
        if not path:
            return
        try:
            self.doc.save(path)
            messagebox.showinfo("Saved", f"PDF saved to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))

    # ─────────────────────────── Page management ──────────────────────────────

    def _prev_page(self):
        if self.doc and self.current_page_idx > 0:
            self._commit_all_boxes()
            self.current_page_idx -= 1
            self._render()

    def _next_page(self):
        if self.doc and self.current_page_idx < self.doc.page_count - 1:
            self._commit_all_boxes()
            self.current_page_idx += 1
            self._render()

    def _rotate(self, angle: int):
        if not self.doc:
            return
        cmd = RotatePageCommand(self.page_service, self.doc,
                                self.current_page_idx, angle)
        cmd.execute()
        self._push_history(cmd)
        self._render()

    def _add_page(self):
        if not self.doc:
            return
        self.doc.insert_page(self.current_page_idx + 1)
        self.current_page_idx += 1
        self._render()

    def _delete_page(self):
        if not self.doc:
            return
        if self.doc.page_count <= 1:
            messagebox.showwarning("Cannot Delete", "A PDF must have at least one page.")
            return
        if not messagebox.askyesno("Delete Page",
                                   f"Delete page {self.current_page_idx + 1}?"):
            return
        self.doc.delete_page(self.current_page_idx)
        self.current_page_idx = min(self.current_page_idx, self.doc.page_count - 1)
        self._render()

    # ─────────────────────────── Zoom ─────────────────────────────────────────

    def _zoom_in(self):
        self._set_zoom(min(MAX_SCALE, self.scale_factor + SCALE_STEP))

    def _zoom_out(self):
        self._set_zoom(max(MIN_SCALE, self.scale_factor - SCALE_STEP))

    def _zoom_reset(self):
        self._set_zoom(RENDER_DPI)

    def _set_zoom(self, new_scale: float):
        self.scale_factor = round(new_scale, 3)
        pct = int(self.scale_factor / RENDER_DPI * 100)
        self._zoom_label.config(text=f"{pct}%")
        self._st_zoom.config(text=f"Zoom {pct}%")
        for box in self._text_boxes:
            box.rescale(self.scale_factor)
        self._render()

    # ─────────────────────────── Rendering ────────────────────────────────────

    def _render(self):
        if not self.doc:
            return
        page     = self.doc.get_page(self.current_page_idx)
        ppm_data = page.render_to_ppm(scale=self.scale_factor)
        self.tk_image = tk.PhotoImage(data=ppm_data)

        cw = self.canvas.winfo_width()
        img_w = int(page.width * self.scale_factor)
        self._page_offset_x = max(20, (cw - img_w) // 2)

        self.canvas.delete("page_bg")
        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")

        # Drop shadow
        ox, oy = self._page_offset_x, self._page_offset_y
        iw = int(page.width  * self.scale_factor)
        ih = int(page.height * self.scale_factor)

        self.canvas.create_rectangle(
            ox + 4, oy + 4, ox + iw + 4, oy + ih + 4,
            fill="#000000", outline="", stipple="gray25",
            tags="page_shadow",
        )
        self.canvas.create_image(ox, oy, anchor=tk.NW, image=self.tk_image, tags="page_img")

        # Update scroll region to fit page + margins
        self.canvas.config(scrollregion=(
            0, 0,
            ox + iw + 40,
            oy + ih + 40,
        ))

        self._page_label.config(
            text=f"{self.current_page_idx + 1} / {self.doc.page_count}")
        self._st_page_size.config(
            text=f"{int(page.width)} × {int(page.height)} pt")

        # Reposition any surviving text boxes
        for box in list(self._text_boxes):
            box.rescale(self.scale_factor)

    def _on_canvas_resize(self, _event=None):
        if self.doc:
            self._render()

    # ─────────────────────────── Canvas events ────────────────────────────────

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple:
        """Convert canvas coords to PDF coords accounting for page offset."""
        pdf_x = (cx - self._page_offset_x) / self.scale_factor
        pdf_y = (cy - self._page_offset_y) / self.scale_factor
        return pdf_x, pdf_y

    def _on_canvas_click(self, event):
        if not self.doc:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        pdf_x, pdf_y = self._canvas_to_pdf(cx, cy)

        tool = self.active_tool.get()
        if tool == "text":
            self._spawn_textbox(cx, cy, pdf_x, pdf_y)
        elif tool == "extract":
            self._handle_extract(pdf_x, pdf_y)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

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

    # ─────────────────────────── Text box lifecycle ───────────────────────────

    def _spawn_textbox(self, cx: float, cy: float, pdf_x: float, pdf_y: float):
        """Creates a new TextBox at the clicked location."""
        page  = self.doc.get_page(self.current_page_idx)
        # Default box size: ~40% page width, 3 lines tall
        pdf_w = page.width * 0.40
        pdf_h = max(self.fontsize * 3, 60)

        box = TextBox(
            canvas     = self.canvas,
            pdf_x      = pdf_x,
            pdf_y      = pdf_y,
            pdf_w      = pdf_w,
            pdf_h      = pdf_h,
            scale      = self.scale_factor,
            font_index = self.font_index,
            fontsize   = self.fontsize,
            color_rgb  = self.text_color,
            on_commit  = self._on_box_confirmed,
            on_delete  = self._on_box_deleted,
        )
        # Offset canvas position to account for page margin
        box.pdf_x = pdf_x
        box.pdf_y = pdf_y
        self._text_boxes.append(box)

    def _on_box_confirmed(self, box: TextBox):
        """Called when user clicks ✓ on a text box. Bakes text into the PDF."""
        self._text_boxes = [b for b in self._text_boxes if b is not box]
        text = box.get_text()
        if not text:
            return

        # Position in PDF space (top-left of text baseline)
        pdf_x  = box.pdf_x
        pdf_y  = box.pdf_y + box.fontsize  # baseline offset

        cmd = InsertTextCommand(
            self.text_service, self.doc,
            self.current_page_idx,
            text,
            (pdf_x, pdf_y),
            box.fontsize,
            box.pdf_font_name,
            box.pdf_color,
        )
        try:
            cmd.execute()
            self._push_history(cmd)
        except Exception as ex:
            messagebox.showerror("Insert Error", str(ex))

        self._render()

    def _on_box_deleted(self, box: TextBox):
        self._text_boxes = [b for b in self._text_boxes if b is not box]

    def _commit_all_boxes(self):
        """Confirm all open text boxes before page change / save."""
        for box in list(self._text_boxes):
            box._confirm()
        self._text_boxes.clear()

    def _dismiss_active_boxes(self):
        """Cancel / remove all open boxes on Escape."""
        for box in list(self._text_boxes):
            box._delete()
        self._text_boxes.clear()

    # ─────────────────────────── Image extraction ─────────────────────────────

    def _handle_extract(self, pdf_x: float, pdf_y: float):
        page   = self.doc.get_page(self.current_page_idx)
        images = page.get_image_info()

        for img in images:
            x0, y0, x1, y1 = img["bbox"]
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                xref = img["xref"]
                try:
                    img_data = self.doc.extract_image_by_xref(xref)
                    ext = img_data.get("ext", "png")
                except Exception as ex:
                    messagebox.showerror("Error", str(ex))
                    return

                out = filedialog.asksaveasfilename(
                    title="Save Extracted Image",
                    defaultextension=f".{ext}",
                    initialfile=f"extracted_image.{ext}",
                )
                if out:
                    cmd = ExtractSingleImageCommand(self.image_service, self.doc, xref, out)
                    cmd.execute()
                    messagebox.showinfo("Extracted", f"Image saved to:\n{out}")
                return

        messagebox.showinfo("No Image Found",
                            "No image detected at that position.\n"
                            "Click directly on an image to extract it.")

    # ─────────────────────────── History ──────────────────────────────────────

    def _push_history(self, cmd):
        # Truncate forward history on new action
        self._history = self._history[:self._history_idx + 1]
        self._history.append(cmd)
        self._history_idx = len(self._history) - 1

    def _undo(self):
        if self._history_idx < 0:
            return
        cmd = self._history[self._history_idx]
        try:
            cmd.undo()
            self._history_idx -= 1
            self._render()
        except NotImplementedError:
            messagebox.showinfo("Undo", "This action cannot be undone.")
        except Exception as ex:
            messagebox.showerror("Undo Error", str(ex))

    # ─────────────────────────── Closing ──────────────────────────────────────

    def _on_closing(self):
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app  = InteractivePDFEditor(root)
    root.mainloop()