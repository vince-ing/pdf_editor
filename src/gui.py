"""
PDF Editor — Modern GUI
  • Draggable grip handle (top-left corner) with hover color + cursor change
  • Text preview font/size matches the baked PDF output exactly
  • Snapshot-based undo for text insertion
  • Smooth zoom, page centering, dark theme
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser
import os

from src.core.document import PDFDocument
from src.services.page_service import PageService
from src.services.image_service import ImageService
from src.services.text_service import TextService
from src.commands.insert_text import InsertTextCommand, InsertTextBoxCommand
from src.commands.insert_image import InsertImageCommand
from src.commands.rotate_page import RotatePageCommand
from src.commands.extract_images import ExtractSingleImageCommand


# ── Design tokens ──────────────────────────────────────────────────────────────
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
    fg_primary   = "#E8E8F0",
    fg_secondary = "#8888AA",
    fg_dim       = "#505068",
    canvas_bg    = "#2B2B3C",
    shadow       = "#09090F",
)

FONT_MONO  = ("Courier", 9)
FONT_UI    = ("Helvetica", 10)
FONT_LABEL = ("Helvetica", 8)

# PDF font list — order must match PDF_FONTS
PDF_FONTS       = ["helv",      "tiro",             "cour",        "zadb",           "symb"   ]
PDF_FONT_LABELS = ["Helvetica", "Times New Roman",  "Courier New", "Zapf Dingbats",  "Symbol" ]
# Tk font families that visually match the PDF fonts
TK_FONT_MAP     = {
    "Helvetica":      "Helvetica",
    "Times New Roman":"Times New Roman",
    "Courier New":    "Courier New",
    "Zapf Dingbats":  "Helvetica",
    "Symbol":         "Helvetica",
}

RENDER_DPI  = 1.5
MIN_SCALE   = 0.3
MAX_SCALE   = 5.0
SCALE_STEP  = 0.15

# Grip handle dimensions
GRIP_W      = 20   # canvas px wide
GRIP_H      = 20   # canvas px tall
GRIP_RADIUS = 4    # corner rounding (not available in tk, used for visual ref)

MIN_BOX_PX  = 60   # minimum box width/height in canvas pixels


# ══════════════════════════════════════════════════════════════════════════════
#  TextBox
# ══════════════════════════════════════════════════════════════════════════════

class TextBox:
    """
    Self-contained draggable, resizable, editable text overlay on a canvas.

    Coordinate system
    -----------------
    All *pdf_* attributes are in PDF user-space (points, origin top-left).
    The box is positioned at (pdf_x, pdf_y) which maps to canvas coords via:

        canvas_x = page_offset_x + pdf_x * scale
        canvas_y = page_offset_y + pdf_y * scale

    The page offsets are injected at construction and kept up-to-date via
    `rescale(scale, page_offset_x, page_offset_y)`.

    Font size
    ---------
    PyMuPDF's insert_text() treats fontsize in PDF points. At scale S, one
    PDF point = S canvas pixels. The Tk entry widget is configured with the
    *same logical fontsize* in points (Tk honours screen DPI). To make the
    preview match the baked output we must account for that DPI difference
    and instead use pixels: tk_fontsize_px = round(fontsize * scale).

    Drag / resize
    -------------
    • Grip handle (top-left): drag to move the whole box.
    • Resize handle (bottom-right ◢): drag to resize.
    • The border itself is NOT draggable — it sits behind the entry widget.
    """

    # Colours
    C_BORDER        = "#7B61FF"
    C_BORDER_HOVER  = "#A594FF"
    C_GRIP          = "#7B61FF"
    C_GRIP_HOVER    = "#FBBF24"   # yellow-amber on hover — unmistakable
    C_RESIZE        = "#7B61FF"
    C_RESIZE_HOVER  = "#34D399"
    C_TOOLBAR_BG    = "#1A1A28"
    C_TOOLBAR_FG    = "#E8E8F0"
    C_ENTRY_BG      = "#FFFFFF"
    C_ENTRY_FG      = "#111111"
    C_ENTRY_SELECT  = "#C4B5FD"

    def __init__(
        self,
        canvas: tk.Canvas,
        pdf_x: float, pdf_y: float,
        pdf_w: float, pdf_h: float,
        scale: float,
        page_offset_x: float,
        page_offset_y: float,
        font_index: int   = 0,
        fontsize: int     = 14,
        color_rgb: tuple  = (0, 0, 0),
        entry_bg: str     = "#FFFFFF",
        align: int        = 0,        # 0=left 1=center 2=right 3=justify
        on_commit = None,
        on_delete = None,
        on_interact = None,
    ):
        self.canvas        = canvas
        self.pdf_x         = pdf_x
        self.pdf_y         = pdf_y
        self.pdf_w         = pdf_w
        self.pdf_h         = pdf_h
        self.scale         = scale
        self.page_offset_x = page_offset_x
        self.page_offset_y = page_offset_y
        self.font_index    = font_index
        self.fontsize      = fontsize
        self.color_rgb     = color_rgb
        self.entry_bg      = entry_bg
        self.align         = align
        self.on_commit     = on_commit
        self.on_delete     = on_delete
        self.on_interact   = on_interact

        # Drag state
        self._drag_start = None
        self._drag_mode  = None   # "move" | "resize"

        # Canvas item IDs
        self._border_id    = None
        self._grip_id      = None
        self._grip_icon_id = None
        self._resize_id    = None
        self._entry_win_id = None
        self._toolbar_win_id = None
        self._all_ids: list = []

        # Tk widgets
        self._toolbar    = None
        self._entry      = None
        self._font_var   = tk.StringVar(value=PDF_FONT_LABELS[font_index])
        self._size_var   = tk.IntVar(value=fontsize)
        self._align_var  = tk.IntVar(value=align)   # 0=L 1=C 2=R 3=J
        self._color_btn  = None

        self._build()

    # ─────────────────────────────── geometry ────────────────────────────────

    def _cx(self) -> float:
        """Canvas x of the box top-left."""
        return self.page_offset_x + self.pdf_x * self.scale

    def _cy(self) -> float:
        """Canvas y of the box top-left."""
        return self.page_offset_y + self.pdf_y * self.scale

    def _cw(self) -> float:
        return max(MIN_BOX_PX, self.pdf_w * self.scale)

    def _ch(self) -> float:
        return max(MIN_BOX_PX * 0.5, self.pdf_h * self.scale)

    def _tk_fontsize(self) -> int:
        """
        Pixel-accurate font size for the Tk preview.
        Tk Spinbox/Text accept negative px sizes (negative = pixels, positive = points).
        We want to fill the box so text *looks* the same size as the baked PDF.
        PyMuPDF fontsize is in PDF points; at scale S, 1pt = S px on canvas.
        """
        return -round(self.fontsize * self.scale)  # negative → Tk treats as pixels

    def _tk_font(self) -> tuple:
        family = TK_FONT_MAP.get(PDF_FONT_LABELS[self.font_index], "Helvetica")
        return (family, self._tk_fontsize())

    # ─────────────────────────────── build ───────────────────────────────────

    def _build(self):
        c  = self.canvas
        cx, cy, cw, ch = self._cx(), self._cy(), self._cw(), self._ch()

        # ── Dashed border (behind everything) ─────────────────────────────────
        self._border_id = c.create_rectangle(
            cx, cy, cx + cw, cy + ch,
            outline=self.C_BORDER, width=2, dash=(5, 3),
        )
        self._all_ids.append(self._border_id)

        # ── Toolbar frame (above the box) ─────────────────────────────────────
        self._toolbar = tk.Frame(c, bg=self.C_TOOLBAR_BG, padx=4, pady=3)
        self._build_toolbar(self._toolbar)
        self._toolbar_win_id = c.create_window(
            cx, cy - 36, anchor=tk.NW, window=self._toolbar)
        self._all_ids.append(self._toolbar_win_id)

        # ── Text entry ────────────────────────────────────────────────────────
        # Get the canvas background colour so the entry blends in seamlessly
        canvas_bg = c.cget("bg")
        self._entry = tk.Text(
            c,
            font=self._tk_font(),
            bg=self.entry_bg,
            fg=self._rgb_hex(self.color_rgb),
            selectbackground=self.C_ENTRY_SELECT,
            insertbackground=self.C_BORDER,
            relief="flat", bd=0,
            highlightthickness=0,
            wrap=tk.WORD, undo=True,
            padx=4, pady=2,
        )
        self._entry_win_id = c.create_window(
            cx, cy, anchor=tk.NW,
            window=self._entry,
            width=max(MIN_BOX_PX, cw),
            height=max(20, ch),
        )
        self._all_ids.append(self._entry_win_id)

        # ── Grip handle — top-left corner, clearly outside the box ───────────
        # A small rounded pill that sticks out to the top-left
        gx1, gy1 = cx - GRIP_W, cy - GRIP_H
        gx2, gy2 = cx + 2,      cy + 2
        self._grip_id = c.create_rectangle(
            gx1, gy1, gx2, gy2,
            fill=self.C_GRIP, outline="#FFFFFF", width=1,
        )
        self._all_ids.append(self._grip_id)

        # Grip icon — 3×3 dots grid drawn as tiny rectangles
        self._grip_dots = self._draw_grip_dots(cx, cy)

        # ── Resize handle — bottom-right ◢ ────────────────────────────────────
        self._resize_id = c.create_polygon(
            0, 0, 0, 0, 0, 0,    # placeholder, placed by _place_handles
            fill=self.C_RESIZE, outline="",
        )
        self._all_ids.append(self._resize_id)
        self._place_handles(cx, cy, cw, ch)

        # ── Bindings ──────────────────────────────────────────────────────────
        # Grip → move
        for item in [self._grip_id] + self._grip_dots:
            c.tag_bind(item, "<Enter>",         self._on_grip_enter)
            c.tag_bind(item, "<Leave>",         self._on_grip_leave)
            c.tag_bind(item, "<ButtonPress-1>", self._on_grip_press)
            c.tag_bind(item, "<B1-Motion>",     self._on_grip_drag)
            c.tag_bind(item, "<ButtonRelease-1>", self._on_grip_release)

        # Resize handle
        c.tag_bind(self._resize_id, "<Enter>",          self._on_resize_enter)
        c.tag_bind(self._resize_id, "<Leave>",          self._on_resize_leave)
        c.tag_bind(self._resize_id, "<ButtonPress-1>",  self._on_resize_press)
        c.tag_bind(self._resize_id, "<B1-Motion>",      self._on_resize_drag)
        c.tag_bind(self._resize_id, "<ButtonRelease-1>",self._on_resize_release)

        # Entry keyboard shortcuts
        self._entry.bind("<Control-Return>", lambda e: self._confirm())
        self._entry.bind("<Escape>",         lambda e: self._delete())

        self._entry.focus_set()
        # Apply initial alignment to the entry widget
        self._set_align(self.align)

    def _build_toolbar(self, parent):
        # Font family
        font_cb = ttk.Combobox(parent, textvariable=self._font_var,
                               values=PDF_FONT_LABELS, state="readonly", width=14)
        font_cb.pack(side=tk.LEFT, padx=(0, 4))
        font_cb.bind("<<ComboboxSelected>>", self._on_font_change)

        # Size
        size_sp = tk.Spinbox(parent, from_=6, to=144, textvariable=self._size_var,
                             width=4, command=self._on_size_change,
                             bg="#252535", fg=self.C_TOOLBAR_FG,
                             buttonbackground="#2A2A3D", relief="flat", highlightthickness=0)
        size_sp.pack(side=tk.LEFT, padx=(0, 4))
        size_sp.bind("<Return>", lambda e: self._on_size_change())

        # Color swatch
        self._color_btn = tk.Button(
            parent, text="  ", relief="flat", bd=1,
            bg=self._rgb_hex(self.color_rgb), width=2,
            cursor="hand2", command=self._pick_color,
            highlightthickness=1, highlightbackground="#555",
        )
        self._color_btn.pack(side=tk.LEFT, padx=(0, 6))

        # Alignment toggle buttons  L C R J
        align_frame = tk.Frame(parent, bg=self.C_TOOLBAR_BG)
        align_frame.pack(side=tk.LEFT, padx=(0, 8))
        self._align_btns = []
        for idx, (symbol, tip) in enumerate([("≡L", "Left"), ("≡C", "Center"),
                                             ("≡R", "Right"), ("≡J", "Justify")]):
            btn = tk.Button(
                align_frame, text=symbol, width=3,
                font=("Helvetica", 8), relief="flat", bd=0,
                padx=3, pady=1, cursor="hand2",
                command=lambda i=idx: self._set_align(i),
            )
            btn.pack(side=tk.LEFT, padx=1)
            self._align_btns.append(btn)
        self._refresh_align_buttons()

        # Confirm
        tk.Button(parent, text="✓  Apply", bg=PALETTE["success"], fg="#0F0F13",
                  font=("Helvetica", 9, "bold"), relief="flat", bd=0,
                  padx=8, pady=1, cursor="hand2",
                  command=self._confirm).pack(side=tk.LEFT, padx=(0, 4))

        # Discard
        tk.Button(parent, text="✕", bg=PALETTE["danger"], fg="#0F0F13",
                  font=("Helvetica", 9, "bold"), relief="flat", bd=0,
                  padx=6, pady=1, cursor="hand2",
                  command=self._delete).pack(side=tk.LEFT)

    def _draw_grip_dots(self, cx: float, cy: float) -> list:
        """Draw a 3×2 dot grid inside the grip area; return list of canvas IDs."""
        c    = self.canvas
        ids  = []
        cols = 3
        rows = 2
        dot  = 2   # dot size px
        pad  = 3   # padding from grip corner
        ox   = cx - GRIP_W + pad
        oy   = cy - GRIP_H + pad
        sx   = (GRIP_W - pad * 2 - dot * cols) / max(cols - 1, 1)
        sy   = (GRIP_H - pad * 2 - dot * rows) / max(rows - 1, 1)
        for r in range(rows):
            for col in range(cols):
                x1 = ox + col * (dot + sx)
                y1 = oy + r   * (dot + sy)
                did = c.create_rectangle(x1, y1, x1 + dot, y1 + dot,
                                         fill="#FFFFFF", outline="")
                ids.append(did)
                self._all_ids.append(did)
        return ids

    def _place_handles(self, cx: float, cy: float, cw: float, ch: float):
        c = self.canvas

        # Grip — top-left, sticking outside the box
        gx1, gy1 = cx - GRIP_W, cy - GRIP_H
        gx2, gy2 = cx + 2,      cy + 2
        c.coords(self._grip_id, gx1, gy1, gx2, gy2)

        # Reposition dot grid
        dot, pad = 2, 3
        ox = cx - GRIP_W + pad
        oy = cy - GRIP_H + pad
        cols, rows = 3, 2
        sx = (GRIP_W - pad * 2 - dot * cols) / max(cols - 1, 1)
        sy = (GRIP_H - pad * 2 - dot * rows) / max(rows - 1, 1)
        dots = self._grip_dots
        i = 0
        for r in range(rows):
            for col in range(cols):
                x1 = ox + col * (dot + sx)
                y1 = oy + r   * (dot + sy)
                if i < len(dots):
                    c.coords(dots[i], x1, y1, x1 + dot, y1 + dot)
                i += 1

        # Resize handle — bottom-right triangle ◢
        ts = 16  # triangle side px
        rx, ry = cx + cw, cy + ch
        c.coords(self._resize_id,
                 rx,      ry - ts,
                 rx,      ry,
                 rx - ts, ry)

    # ─────────────────────────── rescale ─────────────────────────────────────

    def rescale(self, scale: float, page_offset_x: float, page_offset_y: float):
        self.scale         = scale
        self.page_offset_x = page_offset_x
        self.page_offset_y = page_offset_y
        self._reposition()

    def _reposition(self):
        cx, cy, cw, ch = self._cx(), self._cy(), self._cw(), self._ch()
        c = self.canvas
        c.coords(self._border_id, cx, cy, cx + cw, cy + ch)
        c.coords(self._toolbar_win_id, cx, cy - 36)
        c.coords(self._entry_win_id, cx, cy)
        c.itemconfigure(self._entry_win_id, width=max(MIN_BOX_PX, cw),
                        height=max(20, ch))
        # Update entry font to match new scale
        self._entry.config(font=self._tk_font())
        self._place_handles(cx, cy, cw, ch)

    # ─────────────────────────── grip (move) ─────────────────────────────────

    def _on_grip_enter(self, _e):
        self.canvas.config(cursor="fleur")
        self.canvas.itemconfig(self._grip_id, fill=self.C_GRIP_HOVER)

    def _on_grip_leave(self, _e):
        self.canvas.config(cursor="crosshair")
        self.canvas.itemconfig(self._grip_id, fill=self.C_GRIP)

    def _on_grip_press(self, event):
        self._drag_mode  = "move"
        self._drag_start = (event.x_root, event.y_root)
        if self.on_interact:
            self.on_interact()
        return "break"   # stop the event reaching the canvas <Button-1> binding

    def _on_grip_drag(self, event):
        if self._drag_mode != "move" or not self._drag_start:
            return
        dx = (event.x_root - self._drag_start[0]) / self.scale
        dy = (event.y_root - self._drag_start[1]) / self.scale
        self._drag_start = (event.x_root, event.y_root)
        self.pdf_x += dx
        self.pdf_y += dy
        self._reposition()

    def _on_grip_release(self, _e):
        self._drag_mode  = None
        self._drag_start = None

    # ─────────────────────────── resize ──────────────────────────────────────

    def _on_resize_enter(self, _e):
        self.canvas.config(cursor="size_nw_se")
        self.canvas.itemconfig(self._resize_id, fill=self.C_RESIZE_HOVER)

    def _on_resize_leave(self, _e):
        self.canvas.config(cursor="crosshair")
        self.canvas.itemconfig(self._resize_id, fill=self.C_RESIZE)

    def _on_resize_press(self, event):
        self._drag_mode  = "resize"
        self._drag_start = (event.x_root, event.y_root)
        if self.on_interact:
            self.on_interact()
        return "break"   # stop the event reaching the canvas <Button-1> binding

    def _on_resize_drag(self, event):
        if self._drag_mode != "resize" or not self._drag_start:
            return
        dx = (event.x_root - self._drag_start[0]) / self.scale
        dy = (event.y_root - self._drag_start[1]) / self.scale
        self._drag_start = (event.x_root, event.y_root)
        self.pdf_w = max(MIN_BOX_PX / self.scale, self.pdf_w + dx)
        self.pdf_h = max(20          / self.scale, self.pdf_h + dy)
        self._reposition()

    def _on_resize_release(self, _e):
        self._drag_mode  = None
        self._drag_start = None

    # ─────────────────────────── options ─────────────────────────────────────

    def _on_font_change(self, _e=None):
        self.font_index = PDF_FONT_LABELS.index(self._font_var.get())
        self._entry.config(font=self._tk_font())

    def _on_size_change(self, _e=None):
        try:
            self.fontsize = max(6, min(144, int(self._size_var.get())))
        except (ValueError, tk.TclError):
            pass
        self._entry.config(font=self._tk_font())

    def _set_align(self, align: int):
        """Update alignment, refresh button highlights, update entry justify."""
        self.align = align
        self._align_var.set(align)
        self._refresh_align_buttons()
        # Mirror in the Tk Text widget (only left/center/right map; justify≈left)
        tk_justify = ["left", "center", "right", "left"][align]
        self._entry.tag_configure("all", justify=tk_justify)
        self._entry.tag_add("all", "1.0", tk.END)

    def _refresh_align_buttons(self):
        """Highlight the active alignment button, dim the rest."""
        for i, btn in enumerate(self._align_btns):
            if i == self.align:
                btn.config(bg=PALETTE["accent"], fg="#FFFFFF")
            else:
                btn.config(bg="#2A2A3D", fg=self.C_TOOLBAR_FG)

    def _pick_color(self):
        result = colorchooser.askcolor(
            color=self._rgb_hex(self.color_rgb), title="Text Color")
        if result and result[0]:
            self.color_rgb = tuple(int(v) for v in result[0])
            self._color_btn.config(bg=self._rgb_hex(self.color_rgb))
            self._entry.config(fg=self._rgb_hex(self.color_rgb))

    # ─────────────────────────── confirm / delete ─────────────────────────────

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
        if self.on_commit:
            self.on_commit(self)
        self.destroy()

    def _delete(self):
        if self.on_delete:
            self.on_delete(self)
        self.destroy()

    def destroy(self):
        for iid in self._all_ids:
            try:
                self.canvas.delete(iid)
            except Exception:
                pass
        for w in (self._toolbar, self._entry):
            try:
                if w and w.winfo_exists():
                    w.destroy()
            except Exception:
                pass
        self._all_ids.clear()
        self._grip_dots = []

    # ─────────────────────────── helpers ─────────────────────────────────────

    @staticmethod
    def _rgb_hex(rgb: tuple) -> str:
        r, g, b = [max(0, min(255, int(v))) for v in rgb]
        return f"#{r:02x}{g:02x}{b:02x}"

    @property
    def pdf_font_name(self) -> str:
        return PDF_FONTS[self.font_index]

    @property
    def pdf_color(self) -> tuple:
        return tuple(v / 255.0 for v in self.color_rgb)


# ══════════════════════════════════════════════════════════════════════════════
#  Tooltip
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
        tk.Label(tw, text=text, bg="#1C1C26", fg="#E8E8F0",
                 font=("Helvetica", 9), relief="flat", padx=8, pady=4,
                 bd=1, highlightbackground="#2A2A3D",
                 highlightthickness=1).pack()

    def _hide(self, _e=None):
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

        # Document state
        self.doc: PDFDocument | None = None
        self.current_page_idx = 0
        self.scale_factor     = RENDER_DPI
        self.tk_image         = None
        self._page_offset_x   = 20
        self._page_offset_y   = 20
        self._current_path: str | None = None   # path of the open file; None = unsaved
        self._unsaved_changes = False            # True after any mutation

        # Services
        self.page_service  = PageService()
        self.text_service  = TextService()
        self.image_service = ImageService()

        # Tool state
        self.active_tool = tk.StringVar(value="text")
        self.font_index  = 0
        self.fontsize    = 14
        self.text_color  = (0, 0, 0)
        self.text_align  = 0   # 0=left 1=center 2=right 3=justify

        # Active text boxes
        self._text_boxes: list[TextBox] = []
        self._suppress_next_click = False   # set by TextBox grip/resize press

        # Image insertion drag state
        self._img_drag_start: tuple | None = None   # (canvas_x, canvas_y)
        self._img_rubber_band: int | None  = None   # canvas rect item ID
        self._img_pending_path: str | None = None   # file chosen before drag

        # History
        self._history: list    = []
        self._history_idx: int = -1

        self._build_ui()
        self._apply_ttk_style()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ─────────────────────── ttk style ────────────────────────────────────────

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

    # ─────────────────────── UI build ─────────────────────────────────────────

    def _build_ui(self):
        self._build_topbar()
        body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        body.pack(fill=tk.BOTH, expand=True)
        self._build_sidebar(body)
        self._build_canvas_area(body)
        self._build_statusbar()

    def _build_topbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["bg_mid"], height=44)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="◼ PDF Editor", bg=PALETTE["bg_mid"],
                 fg=PALETTE["accent_light"],
                 font=("Helvetica", 13, "bold"), padx=16).pack(side=tk.LEFT)

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=8)

        for label, cmd, tip in [
            ("📂  Open",    self._open_pdf,    "Open PDF  (Ctrl+O)"),
            ("💾  Save",    self._save_pdf,    "Save PDF  (Ctrl+S)"),
            ("📋  Save As", self._save_pdf_as, "Save PDF as new file  (Ctrl+Shift+S)"),
            ("↩  Undo",    self._undo,         "Undo last action  (Ctrl+Z)"),
            ("↪  Redo",    self._redo,         "Redo last undone action  (Ctrl+Y)"),
        ]:
            Tooltip(self._topbar_btn(bar, label, cmd), tip)

        tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
            side=tk.LEFT, fill=tk.Y, pady=8)

        tk.Label(bar, text="Zoom:", bg=PALETTE["bg_mid"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL, padx=8).pack(side=tk.LEFT)
        self._zoom_label = tk.Label(bar, text="100%", bg=PALETTE["bg_mid"],
                                    fg=PALETTE["fg_primary"], font=FONT_MONO, width=5)
        self._zoom_label.pack(side=tk.LEFT)
        Tooltip(self._topbar_btn(bar, "−", self._zoom_out), "Zoom out  (Ctrl+−)")
        Tooltip(self._topbar_btn(bar, "+", self._zoom_in),  "Zoom in   (Ctrl+=)")
        Tooltip(self._topbar_btn(bar, "⟳", self._zoom_reset), "Reset zoom  (Ctrl+0)")

        self._update_zoom_label()

        self.root.bind("<Control-o>",     lambda e: self._open_pdf())
        self.root.bind("<Control-s>",     lambda e: self._save_pdf())
        self.root.bind("<Control-S>",     lambda e: self._save_pdf_as())
        self.root.bind("<Control-z>",     lambda e: self._undo())
        self.root.bind("<Control-y>",     lambda e: self._redo())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>",     lambda e: self._zoom_reset())
        self.root.bind("<Left>",  lambda e: self._prev_page())
        self.root.bind("<Right>", lambda e: self._next_page())
        self.root.bind("<Escape>", lambda e: self._dismiss_boxes())

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

        self._opt_lbl(self._txt_opts, "Font")
        self._sb_font_var = tk.StringVar(value=PDF_FONT_LABELS[self.font_index])
        fc = ttk.Combobox(self._txt_opts, textvariable=self._sb_font_var,
                          values=PDF_FONT_LABELS, state="readonly", width=18)
        fc.pack(fill=tk.X, pady=(0, 8))
        fc.bind("<<ComboboxSelected>>", self._sb_font_change)

        self._opt_lbl(self._txt_opts, "Size (pt)")
        self._sb_size_var = tk.IntVar(value=self.fontsize)
        tk.Spinbox(self._txt_opts, from_=6, to=144, textvariable=self._sb_size_var,
                   width=6, command=self._sb_size_change,
                   bg="#252535", fg=PALETTE["fg_primary"],
                   buttonbackground=PALETTE["border"],
                   relief="flat", highlightthickness=0).pack(anchor="w", pady=(0, 8))

        self._opt_lbl(self._txt_opts, "Color")
        color_row = tk.Frame(self._txt_opts, bg=PALETTE["bg_panel"])
        color_row.pack(fill=tk.X, pady=(0, 8))
        self._color_swatch = tk.Button(
            color_row, text="  ", relief="flat", bd=1, width=3,
            bg="#000000", cursor="hand2", command=self._pick_global_color,
            highlightthickness=1, highlightbackground="#555")
        self._color_swatch.pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(color_row, text="Pick color", bg=PALETTE["bg_panel"],
                 fg=PALETTE["fg_secondary"], font=FONT_LABEL).pack(side=tk.LEFT)

        self._opt_lbl(self._txt_opts, "Alignment")
        align_row = tk.Frame(self._txt_opts, bg=PALETTE["bg_panel"])
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

        self._hint = tk.Label(sb,
            text="Click canvas to place a text box.\n"
                 "Drag the ◢ grip to move.\n"
                 "Ctrl+Z to undo after confirming.",
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
            font=FONT_LABEL, justify="center", wraplength=176)
        self._hint.pack(side=tk.BOTTOM, pady=14)

    def _build_canvas_area(self, parent):
        frame = tk.Frame(parent, bg=PALETTE["bg_dark"])
        frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
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

        self.canvas.bind("<Button-1>",         self._on_canvas_click)
        self.canvas.bind("<B1-Motion>",         self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>",   self._on_canvas_release)
        self.canvas.bind("<MouseWheel>",        self._on_mousewheel)
        self.canvas.bind("<Button-4>",          self._on_mousewheel)
        self.canvas.bind("<Button-5>",          self._on_mousewheel)
        self.canvas.bind("<Control-MouseWheel>",self._on_ctrl_scroll)
        self.canvas.bind("<Control-Button-4>",  self._on_ctrl_scroll)
        self.canvas.bind("<Control-Button-5>",  self._on_ctrl_scroll)
        self.canvas.bind("<Motion>",            self._on_mouse_motion)
        self.canvas.bind("<Configure>",         lambda e: self._render())

    def _build_statusbar(self):
        bar = tk.Frame(self.root, bg=PALETTE["shadow"], height=26)
        bar.pack(side=tk.BOTTOM, fill=tk.X)
        bar.pack_propagate(False)

        def sep():
            tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
                side=tk.LEFT, fill=tk.Y, pady=4)

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
        self._st_zoom = tk.Label(bar, text="",
                                 bg=PALETTE["shadow"], fg=PALETTE["fg_dim"],
                                 font=FONT_MONO, padx=10)
        self._st_zoom.pack(side=tk.RIGHT)

    # ─────────────────────── sidebar helpers ──────────────────────────────────

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=PALETTE["bg_panel"], fg=PALETTE["fg_dim"],
                 font=("Helvetica", 8, "bold"), anchor="w", padx=12).pack(
                     fill=tk.X, pady=(12, 2))
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

    # ─────────────────────── sidebar events ───────────────────────────────────

    def _on_tool_change(self):
        tool = self.active_tool.get()
        self._st_tool.config(text=f"Tool: {tool.replace('_', ' ').title()}")
        # Reset any in-progress image drag
        self._img_drag_cancel()
        if tool == "text":
            self.canvas.config(cursor="crosshair")
            self._txt_opts.pack(fill=tk.X, padx=12, pady=4)
            self._hint.config(
                text="Click canvas to place a text box.\n"
                     "Drag the grip to move it.\n"
                     "Ctrl+Z to undo after confirming.",
                fg=PALETTE["fg_dim"],
            )
        elif tool == "insert_image":
            self.canvas.config(cursor="crosshair")
            self._txt_opts.pack_forget()
            self._hint.config(
                text="Click canvas to choose\nan image file, then drag\nto place it.",
                fg=PALETTE["fg_dim"],
            )
        else:
            self.canvas.config(cursor="arrow")
            self._txt_opts.pack_forget()
            self._hint.config(
                text="Click on an image\nto extract it.",
                fg=PALETTE["fg_dim"],
            )

    def _sb_font_change(self, _=None):
        self.font_index = PDF_FONT_LABELS.index(self._sb_font_var.get())

    def _sb_size_change(self, _=None):
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
            self._color_swatch.config(
                bg="#{:02x}{:02x}{:02x}".format(*self.text_color))

    # ─────────────────────── file operations ──────────────────────────────────

    def _open_pdf(self):
        # Guard against losing unsaved work
        if self._unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes.\nSave before opening a new file?",
            )
            if answer is None:       # Cancel — abort open
                return
            if answer:               # Yes — save first
                if not self._save_pdf():
                    return           # Save was cancelled, abort open

        path = filedialog.askopenfilename(
            title="Open PDF", filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")])
        if not path:
            return
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
        try:
            self.doc = PDFDocument(path)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open:\n{ex}")
            return
        self.current_page_idx  = 0
        self._current_path     = path
        self._unsaved_changes  = False
        self._clear_history()
        self._update_title()
        self._render()

    def _save_pdf(self) -> bool:
        """
        Save to the currently open file path using incremental write.
        Falls back to Save As if no path is known yet (new/unsaved document).
        Returns True on success, False if cancelled or failed.
        """
        if not self.doc:
            return False
        if not self._current_path:
            return self._save_pdf_as()
        self._commit_all_boxes()
        try:
            self.doc.save(self._current_path, incremental=True)
            self._unsaved_changes = False
            self._update_title()
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    def _save_pdf_as(self) -> bool:
        """
        Prompt for a new file path and do a full (non-incremental) save.
        Updates _current_path and title on success.
        Returns True on success, False if cancelled or failed.
        """
        if not self.doc:
            return False
        self._commit_all_boxes()
        path = filedialog.asksaveasfilename(
            title="Save PDF As",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=os.path.basename(self._current_path) if self._current_path else "document.pdf",
        )
        if not path:
            return False
        try:
            self.doc.save(path)
            self._current_path    = path
            self._unsaved_changes = False
            self.doc.path         = path   # keep PDFDocument in sync
            self._update_title()
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    # ─────────────────────── page management ──────────────────────────────────

    def _prev_page(self):
        if self.doc and self.current_page_idx > 0:
            self._commit_all_boxes()
            self._img_drag_cancel()
            self.current_page_idx -= 1
            self._render()

    def _next_page(self):
        if self.doc and self.current_page_idx < self.doc.page_count - 1:
            self._commit_all_boxes()
            self._img_drag_cancel()
            self.current_page_idx += 1
            self._render()

    def _rotate(self, angle: int):
        if not self.doc:
            return
        cmd = RotatePageCommand(self.page_service, self.doc,
                                self.current_page_idx, angle)
        cmd.execute()
        self._push_history(cmd)   # _push_history calls _mark_dirty
        self._render()

    def _add_page(self):
        if not self.doc:
            return
        current = self.doc.get_page(self.current_page_idx)
        self.doc.insert_page(
            self.current_page_idx + 1,
            width=current.width,
            height=current.height,
        )
        self.current_page_idx += 1
        self._mark_dirty()
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
        self._mark_dirty()
        self._render()

    # ─────────────────────── zoom ─────────────────────────────────────────────

    def _zoom_in(self):
        self._set_zoom(min(MAX_SCALE, self.scale_factor + SCALE_STEP))

    def _zoom_out(self):
        self._set_zoom(max(MIN_SCALE, self.scale_factor - SCALE_STEP))

    def _zoom_reset(self):
        self._set_zoom(RENDER_DPI)

    def _set_zoom(self, s: float):
        self.scale_factor = round(s, 3)
        self._update_zoom_label()
        self._render()

    def _update_zoom_label(self):
        pct = int(self.scale_factor / RENDER_DPI * 100)
        self._zoom_label.config(text=f"{pct}%")
        if hasattr(self, "_st_zoom"):
            self._st_zoom.config(text=f"Zoom {pct}%")

    # ─────────────────────── rendering ────────────────────────────────────────

    def _render(self):
        if not self.doc:
            return
        page     = self.doc.get_page(self.current_page_idx)
        ppm      = page.render_to_ppm(scale=self.scale_factor)
        self.tk_image = tk.PhotoImage(data=ppm)

        iw = int(page.width  * self.scale_factor)
        ih = int(page.height * self.scale_factor)

        # Centre the page horizontally in the canvas
        cw = self.canvas.winfo_width()
        self._page_offset_x = max(40, (cw - iw) // 2)
        self._page_offset_y = 30

        ox, oy = self._page_offset_x, self._page_offset_y

        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")

        # Shadow
        self.canvas.create_rectangle(
            ox + 5, oy + 5, ox + iw + 5, oy + ih + 5,
            fill="#000000", outline="", stipple="gray25", tags="page_shadow")
        # Page
        self.canvas.create_image(ox, oy, anchor=tk.NW,
                                 image=self.tk_image, tags="page_img")

        self.canvas.config(scrollregion=(0, 0, ox + iw + 50, oy + ih + 50))

        self._page_label.config(
            text=f"{self.current_page_idx + 1} / {self.doc.page_count}")
        self._st_size.config(text=f"{int(page.width)} × {int(page.height)} pt")

        # Reposition open text boxes for new offset/scale
        for box in list(self._text_boxes):
            box.rescale(self.scale_factor, self._page_offset_x, self._page_offset_y)

    # ─────────────────────── canvas events ────────────────────────────────────

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple:
        px = (cx - self._page_offset_x) / self.scale_factor
        py = (cy - self._page_offset_y) / self.scale_factor
        return px, py

    def _on_canvas_click(self, event):
        if not self.doc:
            return
        # A TextBox grip/resize press fires before this canvas binding.
        # If it set the flag, skip spawning a new box this click.
        if self._suppress_next_click:
            self._suppress_next_click = False
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        pdf_x, pdf_y = self._canvas_to_pdf(cx, cy)

        if self.active_tool.get() == "text":
            self._spawn_textbox(pdf_x, pdf_y)
        elif self.active_tool.get() == "extract":
            self._handle_extract(pdf_x, pdf_y)
        elif self.active_tool.get() == "insert_image":
            if self._img_pending_path is None:
                # First click: pick the file. Drag begins on the NEXT press.
                self._img_pick_file()
            else:
                # Second click: start the rubber-band drag.
                self._img_drag_start  = (cx, cy)
                self._img_rubber_band = None

    def _on_canvas_drag(self, event):
        if self.active_tool.get() != "insert_image":
            return
        if self._img_drag_start is None:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        x0, y0 = self._img_drag_start
        if self._img_rubber_band is None:
            self._img_rubber_band = self.canvas.create_rectangle(
                x0, y0, cx, cy,
                outline=PALETTE["accent_light"], width=2, dash=(5, 3),
            )
        else:
            self.canvas.coords(self._img_rubber_band, x0, y0, cx, cy)

    def _on_canvas_release(self, event):
        if self.active_tool.get() != "insert_image":
            return
        if self._img_drag_start is None:
            return

        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        x0, y0 = self._img_drag_start
        pending_path = self._img_pending_path  # capture before cancel clears it

        # Remove rubber band and reset drag state (but keep pending path until used)
        if self._img_rubber_band is not None:
            self.canvas.delete(self._img_rubber_band)
            self._img_rubber_band = None
        self._img_drag_start = None

        # Require a minimum drag size to avoid accidental placements
        if abs(cx - x0) < 10 or abs(cy - y0) < 10:
            return

        if not pending_path:
            return

        self._img_pending_path = None  # consumed

        px0, py0 = self._canvas_to_pdf(min(x0, cx), min(y0, cy))
        px1, py1 = self._canvas_to_pdf(max(x0, cx), max(y0, cy))

        cmd = InsertImageCommand(
            self.image_service, self.doc,
            self.current_page_idx,
            (px0, py0, px1, py1),
            pending_path,
        )
        try:
            cmd.execute()
            self._push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Insert Image Error", str(ex))
            return
        self._render()

    def _img_pick_file(self):
        """Open file dialog to choose an image. Stores path for the next drag."""
        path = filedialog.askopenfilename(
            title="Choose Image to Insert — then drag to place it",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.gif"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        self._img_pending_path = path
        # Give the user a visual cue that a file is loaded and ready to place
        self._hint.config(
            text=f"✓ {os.path.basename(path)}\n\nNow drag on the canvas\nto place the image.",
            fg=PALETTE["success"],
        )

    def _img_drag_cancel(self):
        """Remove the rubber band and fully reset insertion drag state."""
        if self._img_rubber_band is not None:
            self.canvas.delete(self._img_rubber_band)
            self._img_rubber_band = None
        self._img_drag_start   = None
        self._img_pending_path = None
        # Reset hint text if insert_image tool is still active
        if self.active_tool.get() == "insert_image":
            self._hint.config(
                text="Click canvas to choose\nan image file, then drag\nto place it.",
                fg=PALETTE["fg_dim"],
            )

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

    # ─────────────────────── text box lifecycle ───────────────────────────────

    def _spawn_textbox(self, pdf_x: float, pdf_y: float):
        page  = self.doc.get_page(self.current_page_idx)
        pdf_w = page.width * 0.42
        pdf_h = self.fontsize * 4

        # Sample the pixel colour from the rendered page at the click point so
        # the text entry background blends in — giving a "transparent" appearance.
        bg_color = self._sample_page_color(pdf_x, pdf_y)

        box = TextBox(
            canvas        = self.canvas,
            pdf_x         = pdf_x,
            pdf_y         = pdf_y,
            pdf_w         = pdf_w,
            pdf_h         = pdf_h,
            scale         = self.scale_factor,
            page_offset_x = self._page_offset_x,
            page_offset_y = self._page_offset_y,
            font_index    = self.font_index,
            fontsize      = self.fontsize,
            color_rgb     = self.text_color,
            entry_bg      = bg_color,
            align         = self.text_align,
            on_commit     = self._on_box_confirmed,
            on_delete     = self._on_box_deleted,
            on_interact   = self._on_box_interact,
        )
        self._text_boxes.append(box)

    def _sample_page_color(self, pdf_x: float, pdf_y: float) -> str:
        """
        Sample a pixel from the rendered tk_image at the given PDF coordinates.
        Falls back to the canvas background if the image isn't available or the
        point is outside the page.
        """
        canvas_fallback = self.canvas.cget("bg")
        if self.tk_image is None:
            return canvas_fallback
        try:
            ix = int(pdf_x * self.scale_factor)
            iy = int(pdf_y * self.scale_factor)
            r, g, b = self.tk_image.get(ix, iy)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return canvas_fallback

    def _on_box_confirmed(self, box: TextBox):
        self._text_boxes = [b for b in self._text_boxes if b is not box]
        text = box.get_text()
        if not text:
            return

        # Use insert_textbox so text word-wraps within the box bounds and
        # alignment is honoured. The rect maps directly from the overlay box.
        rect = (box.pdf_x, box.pdf_y,
                box.pdf_x + box.pdf_w, box.pdf_y + box.pdf_h)

        cmd = InsertTextBoxCommand(
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
        """Called when a TextBox grip/resize is pressed. Prevents canvas click spawning a new box."""
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

    # ─────────────────────── image extraction ────────────────────────────────

    def _handle_extract(self, pdf_x: float, pdf_y: float):
        page   = self.doc.get_page(self.current_page_idx)
        images = page.get_image_info()
        for img in images:
            x0, y0, x1, y1 = img["bbox"]
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                xref = img["xref"]
                try:
                    data = self.doc.extract_image_by_xref(xref)
                    ext  = data.get("ext", "png")
                except Exception as ex:
                    messagebox.showerror("Error", str(ex))
                    return
                out = filedialog.asksaveasfilename(
                    title="Save Image",
                    defaultextension=f".{ext}",
                    initialfile=f"extracted.{ext}")
                if out:
                    ExtractSingleImageCommand(
                        self.image_service, self.doc, xref, out).execute()
                    messagebox.showinfo("Extracted", f"Saved to:\n{out}")
                return
        messagebox.showinfo("No Image",
                            "No image found at that position.\n"
                            "Click directly on an image.")

    # ─────────────────────── history ─────────────────────────────────────────

    def _update_title(self):
        """Reflect current file name and unsaved-changes indicator in the window title."""
        if self._current_path:
            name = os.path.basename(self._current_path)
            marker = " •" if self._unsaved_changes else ""
            self.root.title(f"PDF Editor — {name}{marker}")
        else:
            self.root.title("PDF Editor — Untitled •" if self._unsaved_changes
                            else "PDF Editor")

    def _mark_dirty(self):
        """Mark the document as having unsaved changes."""
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    def _push_history(self, cmd):
        # Discard (and clean up) any forward history that is now unreachable.
        discarded = self._history[self._history_idx + 1:]
        for old_cmd in discarded:
            old_cmd.cleanup()
        self._history = self._history[:self._history_idx + 1]
        self._history.append(cmd)
        self._history_idx = len(self._history) - 1
        self._mark_dirty()

    def _clear_history(self):
        """Clean up all snapshot files and reset the history stack."""
        for cmd in self._history:
            cmd.cleanup()
        self._history.clear()
        self._history_idx = -1

    def _undo(self):
        if self._history_idx < 0:
            return
        cmd = self._history[self._history_idx]
        try:
            cmd.undo()
            self._history_idx -= 1
            self._mark_dirty()
            self._render()
        except NotImplementedError:
            messagebox.showinfo("Undo", "This action cannot be undone.")
        except Exception as ex:
            messagebox.showerror("Undo Error", str(ex))

    def _redo(self):
        if self._history_idx >= len(self._history) - 1:
            return
        cmd = self._history[self._history_idx + 1]
        try:
            cmd.execute()
            self._history_idx += 1
            self._mark_dirty()
            self._render()
        except Exception as ex:
            messagebox.showerror("Redo Error", str(ex))

    # ─────────────────────── closing ─────────────────────────────────────────

    def _on_closing(self):
        if self._unsaved_changes:
            answer = messagebox.askyesnocancel(
                "Unsaved Changes",
                "You have unsaved changes.\nSave before closing?",
            )
            if answer is None:   # Cancel
                return
            if answer:           # Yes — save
                if not self._save_pdf():
                    return       # Save was cancelled, don't close
        self._commit_all_boxes()
        self._img_drag_cancel()
        self._clear_history()
        if self.doc:
            self.doc.close()
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    InteractivePDFEditor(root)
    root.mainloop()