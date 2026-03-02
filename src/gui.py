import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

from src.core.document import PDFDocument
from src.services.page_service import PageService
from src.services.image_service import ImageService
from src.services.text_service import TextService
from src.commands.insert_text import InsertTextCommand
from src.commands.extract_images import ExtractSingleImageCommand


# ── Fonts available in PyMuPDF (fitz built-ins) ──────────────────────────────
PDF_FONTS = ["helv", "tiro", "cour", "zadb", "symb"]
PDF_FONT_LABELS = ["Helvetica", "Times Roman", "Courier", "Zapf Dingbats", "Symbol"]


class FloatingTextOverlay:
    """
    A self-contained, interactive text overlay drawn on top of the PDF canvas.

    Lifecycle:
        1. Created on mouse-click in 'text' tool mode.
        2. User types text, adjusts font/size via the mini-toolbar.
        3. ✓ Confirm  → calls on_confirm(text, pdf_x, pdf_y, font, fontsize)
           ✕ Cancel   → calls on_cancel(), all canvas items are cleaned up.

    The overlay never writes to the PDF itself — it only signals back via callbacks.
    """

    BORDER_COLOR   = "#3A7BF7"  # Blue dashed border
    TOOLBAR_BG     = "#1E1E2E"  # Dark toolbar background
    TOOLBAR_FG     = "#CDD6F4"  # Light text
    CONFIRM_COLOR  = "#A6E3A1"  # Green confirm button
    CANCEL_COLOR   = "#F38BA8"  # Red cancel button
    HANDLE_SIZE    = 8          # px — corner drag handle square

    def __init__(
        self,
        canvas: tk.Canvas,
        canvas_x: float,
        canvas_y: float,
        pdf_x: float,
        pdf_y: float,
        initial_font_index: int,
        initial_fontsize: int,
        on_confirm,   # callable(text, pdf_x, pdf_y, font_key, fontsize)
        on_cancel,    # callable()
    ):
        self.canvas      = canvas
        self.pdf_x       = pdf_x
        self.pdf_y       = pdf_y
        self.on_confirm  = on_confirm
        self.on_cancel   = on_cancel

        # ── Overlay state ─────────────────────────────────────────────────────
        self._font_index = initial_font_index
        self._fontsize   = initial_fontsize
        self._drag_start = None   # (event.x, event.y) when dragging begins
        self._box_x      = canvas_x
        self._box_y      = canvas_y
        self._width      = 240    # initial overlay width in canvas px
        self._destroyed  = False

        # ── Canvas item IDs (for cleanup) ─────────────────────────────────────
        self._ids = []

        # ── Build the overlay ─────────────────────────────────────────────────
        self._build(canvas_x, canvas_y)

    # ─────────────────────────────── Build ───────────────────────────────────

    def _build(self, cx: float, cy: float):
        """Draws all canvas widgets and elements for the overlay."""
        c = self.canvas

        # ── Mini-toolbar (drawn as a real tk.Frame embedded in the canvas) ────
        self._toolbar_frame = tk.Frame(c, bg=self.TOOLBAR_BG, padx=4, pady=3, relief="flat")

        # Font family dropdown
        self._font_var = tk.StringVar(value=PDF_FONT_LABELS[self._font_index])
        font_menu = ttk.Combobox(
            self._toolbar_frame,
            textvariable=self._font_var,
            values=PDF_FONT_LABELS,
            width=11,
            state="readonly",
        )
        font_menu.pack(side=tk.LEFT, padx=(0, 4))
        font_menu.bind("<<ComboboxSelected>>", self._on_font_change)

        # Font-size spinner
        self._size_var = tk.IntVar(value=self._fontsize)
        size_spin = tk.Spinbox(
            self._toolbar_frame,
            from_=6, to=120,
            textvariable=self._size_var,
            width=4,
            command=self._on_size_change,
            bg=self.TOOLBAR_BG,
            fg=self.TOOLBAR_FG,
            buttonbackground="#313244",
            relief="flat",
            highlightthickness=0,
        )
        size_spin.pack(side=tk.LEFT, padx=(0, 8))
        size_spin.bind("<Return>", lambda e: self._on_size_change())

        # Confirm button
        tk.Button(
            self._toolbar_frame,
            text="✓ Confirm",
            bg=self.CONFIRM_COLOR,
            fg="#1E1E2E",
            font=("Helvetica", 9, "bold"),
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            command=self._confirm,
        ).pack(side=tk.LEFT, padx=(0, 4))

        # Cancel button
        tk.Button(
            self._toolbar_frame,
            text="✕",
            bg=self.CANCEL_COLOR,
            fg="#1E1E2E",
            font=("Helvetica", 9, "bold"),
            relief="flat",
            bd=0,
            padx=6,
            cursor="hand2",
            command=self._cancel,
        ).pack(side=tk.LEFT)

        toolbar_win = c.create_window(cx, cy - 32, anchor=tk.NW, window=self._toolbar_frame)
        self._ids.append(toolbar_win)

        # ── Dashed border rectangle ───────────────────────────────────────────
        self._border = c.create_rectangle(
            cx, cy, cx + self._width, cy + self._fontsize + 16,
            outline=self.BORDER_COLOR, width=1, dash=(5, 3),
        )
        self._ids.append(self._border)

        # ── Drag-handle (top-left corner square) ─────────────────────────────
        hs = self.HANDLE_SIZE
        self._handle = c.create_rectangle(
            cx - hs // 2, cy - hs // 2, cx + hs // 2, cy + hs // 2,
            fill=self.BORDER_COLOR, outline="",
        )
        self._ids.append(self._handle)

        # ── Inline text entry widget ──────────────────────────────────────────
        self._entry_var = tk.StringVar()
        self._entry = tk.Entry(
            c,
            textvariable=self._entry_var,
            font=self._make_tk_font(),
            relief="flat",
            bd=0,
            bg="#FFFFFF",
            fg="#000000",
            insertbackground=self.BORDER_COLOR,
            highlightthickness=0,
        )
        self._entry_win = c.create_window(
            cx + 4, cy + 4, anchor=tk.NW,
            window=self._entry,
            width=self._width - 8,
        )
        self._ids.append(self._entry_win)

        # ── Bind drag events to toolbar + handle ──────────────────────────────
        for widget in (self._toolbar_frame,):
            widget.bind("<ButtonPress-1>",   self._drag_start_event)
            widget.bind("<B1-Motion>",       self._drag_motion_event)
            widget.bind("<ButtonRelease-1>", self._drag_end_event)

        c.tag_bind(self._handle, "<ButtonPress-1>",   self._drag_start_event)
        c.tag_bind(self._handle, "<B1-Motion>",       self._drag_motion_event)
        c.tag_bind(self._handle, "<ButtonRelease-1>", self._drag_end_event)

        # ── Keyboard shortcuts ────────────────────────────────────────────────
        self._entry.bind("<Return>",  lambda e: self._confirm())
        self._entry.bind("<Escape>",  lambda e: self._cancel())
        self._entry.bind("<KeyRelease>", self._on_text_change)

        self._entry.focus_set()
        self._update_border_height()

    # ─────────────────────────── Event Handlers ───────────────────────────────

    def _on_font_change(self, _event=None):
        label = self._font_var.get()
        self._font_index = PDF_FONT_LABELS.index(label)
        self._entry.config(font=self._make_tk_font())
        self._update_border_height()

    def _on_size_change(self, _event=None):
        try:
            self._fontsize = max(6, min(120, int(self._size_var.get())))
        except (ValueError, tk.TclError):
            pass
        self._entry.config(font=self._make_tk_font())
        self._update_border_height()

    def _on_text_change(self, _event=None):
        """Widen the border as the user types."""
        text = self._entry_var.get()
        char_width_approx = self._fontsize * 0.6
        new_width = max(240, int(len(text) * char_width_approx) + 24)
        if new_width != self._width:
            self._width = new_width
            self.canvas.itemconfigure(self._entry_win, width=self._width - 8)
            self._update_border()

    def _drag_start_event(self, event):
        self._drag_start = (event.x_root, event.y_root)

    def _drag_motion_event(self, event):
        if self._drag_start is None:
            return
        dx = event.x_root - self._drag_start[0]
        dy = event.y_root - self._drag_start[1]
        self._drag_start = (event.x_root, event.y_root)
        self._box_x += dx
        self._box_y += dy
        self._update_border()

    def _drag_end_event(self, _event):
        self._drag_start = None

    # ─────────────────────────── Confirm / Cancel ─────────────────────────────

    def _confirm(self):
        if self._destroyed:
            return
        text = self._entry_var.get().strip()
        if not text:
            self._cancel()
            return
        font_key  = PDF_FONTS[self._font_index]
        fontsize  = self._fontsize
        pdf_x     = self.pdf_x
        pdf_y     = self.pdf_y
        self._destroy()
        self.on_confirm(text, pdf_x, pdf_y, font_key, fontsize)

    def _cancel(self):
        if self._destroyed:
            return
        self._destroy()
        self.on_cancel()

    # ──────────────────────────── Helpers ────────────────────────────────────

    def _make_tk_font(self) -> tuple:
        label = PDF_FONT_LABELS[self._font_index]
        # Map PDF font keys to Tk font families for the live preview
        tk_families = {
            "Helvetica":      "Helvetica",
            "Times Roman":    "Times New Roman",
            "Courier":        "Courier New",
            "Zapf Dingbats":  "Helvetica",
            "Symbol":         "Helvetica",
        }
        return (tk_families.get(label, "Helvetica"), self._fontsize)

    def _update_border_height(self):
        self._update_border()

    def _update_border(self):
        c    = self.canvas
        cx   = self._box_x
        cy   = self._box_y
        h    = self._fontsize + 16
        hs   = self.HANDLE_SIZE

        c.coords(self._border, cx, cy, cx + self._width, cy + h)
        c.coords(self._handle,
                 cx - hs // 2, cy - hs // 2,
                 cx + hs // 2, cy + hs // 2)
        c.itemconfigure(self._entry_win, width=self._width - 8)
        c.coords(self._entry_win, cx + 4, cy + 4)
        c.coords(self._ids[0], cx, cy - 32)  # toolbar window

    def _destroy(self):
        """Remove all canvas items and embedded widgets."""
        if self._destroyed:
            return
        self._destroyed = True
        for item_id in self._ids:
            try:
                self.canvas.delete(item_id)
            except Exception:
                pass
        try:
            self._toolbar_frame.destroy()
        except Exception:
            pass
        try:
            self._entry.destroy()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  Main Application
# ══════════════════════════════════════════════════════════════════════════════

class InteractivePDFEditor:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PDF Editor")
        self.root.geometry("1000x750")
        self.root.configure(bg="#1E1E2E")

        # ── Document state ────────────────────────────────────────────────────
        self.doc               = None
        self.current_page_idx  = 0
        self.scale_factor      = 1.5
        self.tk_image          = None

        # ── Services ──────────────────────────────────────────────────────────
        self.text_service  = TextService()
        self.image_service = ImageService()

        # ── Active tool + text options ────────────────────────────────────────
        self.active_tool      = tk.StringVar(value="text")
        self.font_index       = 0    # index into PDF_FONTS / PDF_FONT_LABELS
        self.fontsize         = 14

        # ── Active floating overlay (only one at a time) ───────────────────────
        self._active_overlay: FloatingTextOverlay | None = None

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    # ─────────────────────────────── UI Build ─────────────────────────────────

    def _build_ui(self):
        # ── Top menu bar ──────────────────────────────────────────────────────
        menubar = tk.Menu(self.root, bg="#313244", fg="#CDD6F4", activebackground="#45475A",
                          activeforeground="#CDD6F4", relief="flat")
        file_menu = tk.Menu(menubar, tearoff=0, bg="#313244", fg="#CDD6F4",
                            activebackground="#45475A")
        file_menu.add_command(label="Open…        Ctrl+O", command=self._open_pdf)
        file_menu.add_command(label="Save As…     Ctrl+S", command=self._save_pdf)
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self._on_closing)
        menubar.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menubar)

        # Keyboard shortcuts
        self.root.bind("<Control-o>", lambda e: self._open_pdf())
        self.root.bind("<Control-s>", lambda e: self._save_pdf())
        self.root.bind("<Left>",      lambda e: self._prev_page())
        self.root.bind("<Right>",     lambda e: self._next_page())
        self.root.bind("<Escape>",    lambda e: self._cancel_active_overlay())

        # ── Main layout: sidebar + canvas ─────────────────────────────────────
        main = tk.Frame(self.root, bg="#1E1E2E")
        main.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar(main)
        self._build_canvas_area(main)
        self._build_status_bar()

    def _build_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg="#181825", width=180)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)

        # ── Section: File ─────────────────────────────────────────────────────
        self._sidebar_section(sidebar, "FILE")
        self._sidebar_btn(sidebar, "📂  Open PDF",   self._open_pdf)
        self._sidebar_btn(sidebar, "💾  Save As…",   self._save_pdf)

        # ── Section: Pages ────────────────────────────────────────────────────
        self._sidebar_section(sidebar, "NAVIGATION")
        nav = tk.Frame(sidebar, bg="#181825")
        nav.pack(fill=tk.X, padx=10, pady=4)
        tk.Button(nav, text="◀", command=self._prev_page, **self._btn_style_small()).pack(side=tk.LEFT)
        self.lbl_page = tk.Label(nav, text="—", bg="#181825", fg="#CDD6F4",
                                 font=("Helvetica", 10))
        self.lbl_page.pack(side=tk.LEFT, expand=True)
        tk.Button(nav, text="▶", command=self._next_page, **self._btn_style_small()).pack(side=tk.RIGHT)

        # ── Section: Tools ────────────────────────────────────────────────────
        self._sidebar_section(sidebar, "TOOLS")

        for label, value in [("📝  Add Text", "text"), ("🖼  Extract Image", "extract")]:
            rb = tk.Radiobutton(
                sidebar, text=label, variable=self.active_tool, value=value,
                bg="#181825", fg="#CDD6F4", selectcolor="#313244",
                activebackground="#181825", activeforeground="#A6E3A1",
                font=("Helvetica", 10), anchor="w", cursor="hand2",
                command=self._on_tool_change,
            )
            rb.pack(fill=tk.X, padx=10, pady=2)

        # ── Section: Text Options (contextual) ────────────────────────────────
        self._sidebar_section(sidebar, "TEXT OPTIONS")

        self._text_options_frame = tk.Frame(sidebar, bg="#181825")
        self._text_options_frame.pack(fill=tk.X, padx=10, pady=4)

        tk.Label(self._text_options_frame, text="Font", bg="#181825",
                 fg="#6C7086", font=("Helvetica", 9)).pack(anchor="w")
        self._sb_font_var = tk.StringVar(value=PDF_FONT_LABELS[self.font_index])
        font_combo = ttk.Combobox(
            self._text_options_frame, textvariable=self._sb_font_var,
            values=PDF_FONT_LABELS, state="readonly", width=16,
        )
        font_combo.pack(fill=tk.X, pady=(0, 6))
        font_combo.bind("<<ComboboxSelected>>", self._sb_on_font_change)

        tk.Label(self._text_options_frame, text="Size", bg="#181825",
                 fg="#6C7086", font=("Helvetica", 9)).pack(anchor="w")
        self._sb_size_var = tk.IntVar(value=self.fontsize)
        size_spin = tk.Spinbox(
            self._text_options_frame, from_=6, to=120,
            textvariable=self._sb_size_var, width=6,
            command=self._sb_on_size_change,
            bg="#313244", fg="#CDD6F4", buttonbackground="#45475A",
            relief="flat", highlightthickness=0,
        )
        size_spin.pack(anchor="w", pady=(0, 4))
        size_spin.bind("<Return>", lambda e: self._sb_on_size_change())

        # ── Hint label at bottom of sidebar ───────────────────────────────────
        self._hint_label = tk.Label(
            sidebar, text="Click the canvas\nto place text.",
            bg="#181825", fg="#585B70", font=("Helvetica", 9),
            justify="center", wraplength=160,
        )
        self._hint_label.pack(side=tk.BOTTOM, pady=12)

    def _build_canvas_area(self, parent):
        canvas_frame = tk.Frame(parent, bg="#1E1E2E")
        canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.v_scroll = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll = ttk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas = tk.Canvas(
            canvas_frame, bg="#313244",
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
            cursor="crosshair",
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.v_scroll.config(command=self.canvas.yview)
        self.h_scroll.config(command=self.canvas.xview)

        self.canvas.bind("<Button-1>",    self._on_canvas_click)
        self.canvas.bind("<MouseWheel>",  self._on_mousewheel)     # Windows/macOS
        self.canvas.bind("<Button-4>",    self._on_mousewheel)     # Linux scroll up
        self.canvas.bind("<Button-5>",    self._on_mousewheel)     # Linux scroll down
        self.canvas.bind("<Motion>",      self._on_mouse_motion)

    def _build_status_bar(self):
        bar = tk.Frame(self.root, bg="#11111B", height=24)
        bar.pack(side=tk.BOTTOM, fill=tk.X)

        self._status_tool  = tk.Label(bar, text="Tool: —", bg="#11111B", fg="#6C7086",
                                      font=("Helvetica", 9), padx=8)
        self._status_tool.pack(side=tk.LEFT)

        tk.Frame(bar, bg="#313244", width=1).pack(side=tk.LEFT, fill=tk.Y, pady=4)

        self._status_coords = tk.Label(bar, text="x: —   y: —", bg="#11111B",
                                       fg="#6C7086", font=("Courier", 9), padx=8)
        self._status_coords.pack(side=tk.LEFT)

        tk.Frame(bar, bg="#313244", width=1).pack(side=tk.LEFT, fill=tk.Y, pady=4)

        self._status_zoom = tk.Label(bar, text=f"Zoom: {int(self.scale_factor*100)}%",
                                     bg="#11111B", fg="#6C7086", font=("Helvetica", 9), padx=8)
        self._status_zoom.pack(side=tk.RIGHT)

    # ──────────────────── Sidebar helpers ─────────────────────────────────────

    @staticmethod
    def _sidebar_section(parent, title: str):
        tk.Label(parent, text=title, bg="#181825", fg="#585B70",
                 font=("Helvetica", 8, "bold"), anchor="w", padx=10
                 ).pack(fill=tk.X, pady=(12, 2))
        tk.Frame(parent, bg="#313244", height=1).pack(fill=tk.X, padx=10)

    @staticmethod
    def _sidebar_btn(parent, text: str, command) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=command,
            bg="#181825", fg="#CDD6F4", activebackground="#313244",
            activeforeground="#A6E3A1", font=("Helvetica", 10),
            relief="flat", bd=0, padx=10, pady=5, anchor="w", cursor="hand2",
        )
        btn.pack(fill=tk.X, padx=4, pady=1)
        return btn

    @staticmethod
    def _btn_style_small() -> dict:
        return dict(bg="#313244", fg="#CDD6F4", activebackground="#45475A",
                    relief="flat", bd=0, padx=8, pady=2, font=("Helvetica", 10))

    # ──────────────────── Sidebar event handlers ──────────────────────────────

    def _on_tool_change(self):
        self._cancel_active_overlay()
        tool = self.active_tool.get()
        self._status_tool.config(text=f"Tool: {tool.replace('_', ' ').title()}")

        # Show/hide text options contextually
        if tool == "text":
            self._text_options_frame.pack(fill=tk.X, padx=10, pady=4)
            self._hint_label.config(text="Click the canvas\nto place text.")
            self.canvas.config(cursor="crosshair")
        else:
            self._text_options_frame.pack_forget()
            self._hint_label.config(text="Click on an image\nto extract it.")
            self.canvas.config(cursor="arrow")

    def _sb_on_font_change(self, _event=None):
        label = self._sb_font_var.get()
        self.font_index = PDF_FONT_LABELS.index(label)

    def _sb_on_size_change(self, _event=None):
        try:
            self.fontsize = max(6, min(120, int(self._sb_size_var.get())))
        except (ValueError, tk.TclError):
            pass

    # ──────────────────── File operations ─────────────────────────────────────

    def _open_pdf(self):
        filepath = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not filepath:
            return
        if self.doc:
            self.doc.close()
        self.doc = PDFDocument(filepath)
        self.current_page_idx = 0
        self.root.title(f"PDF Editor — {os.path.basename(filepath)}")
        self._render_current_page()

    def _save_pdf(self):
        if not self.doc:
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")]
        )
        if filepath:
            self.doc.save(filepath)
            messagebox.showinfo("Saved", f"Saved to:\n{filepath}")

    # ──────────────────── Navigation & rendering ──────────────────────────────

    def _prev_page(self):
        if self.doc and self.current_page_idx > 0:
            self._cancel_active_overlay()
            self.current_page_idx -= 1
            self._render_current_page()

    def _next_page(self):
        if self.doc and self.current_page_idx < (self.doc.page_count - 1):
            self._cancel_active_overlay()
            self.current_page_idx += 1
            self._render_current_page()

    def _render_current_page(self):
        if not self.doc:
            return
        page     = self.doc.get_page(self.current_page_idx)
        ppm_data = page.render_to_ppm(scale=self.scale_factor)

        self.tk_image = tk.PhotoImage(data=ppm_data)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        total = self.doc.page_count
        self.lbl_page.config(text=f"{self.current_page_idx + 1} / {total}")

    # ──────────────────── Canvas events ───────────────────────────────────────

    def _on_canvas_click(self, event):
        if not self.doc:
            return

        # If there's an existing overlay, dismiss it first on a second click
        if self._active_overlay:
            # Let the overlay's own bindings handle confirm/cancel;
            # a click outside it cancels it.
            self._cancel_active_overlay()
            return

        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        pdf_x    = canvas_x / self.scale_factor
        pdf_y    = canvas_y / self.scale_factor

        if self.active_tool.get() == "text":
            self._spawn_text_overlay(canvas_x, canvas_y, pdf_x, pdf_y)
        elif self.active_tool.get() == "extract":
            self._handle_extract_tool(pdf_x, pdf_y)

    def _on_mousewheel(self, event):
        if event.num == 4:      # Linux scroll up
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:    # Linux scroll down
            self.canvas.yview_scroll(1, "units")
        else:                   # Windows / macOS
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_mouse_motion(self, event):
        if not self.doc:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px = cx / self.scale_factor
        py = cy / self.scale_factor
        self._status_coords.config(text=f"x: {px:6.1f}   y: {py:6.1f}")

    # ──────────────────── Text overlay lifecycle ───────────────────────────────

    def _spawn_text_overlay(self, canvas_x, canvas_y, pdf_x, pdf_y):
        self._active_overlay = FloatingTextOverlay(
            canvas       = self.canvas,
            canvas_x     = canvas_x,
            canvas_y     = canvas_y,
            pdf_x        = pdf_x,
            pdf_y        = pdf_y,
            initial_font_index = self.font_index,
            initial_fontsize   = self.fontsize,
            on_confirm   = self._on_text_confirmed,
            on_cancel    = self._on_text_cancelled,
        )

    def _on_text_confirmed(self, text: str, pdf_x: float, pdf_y: float,
                            font_key: str, fontsize: int):
        self._active_overlay = None
        # Sync sidebar defaults back to whatever the user chose in the overlay
        self.fontsize    = fontsize
        self.font_index  = PDF_FONTS.index(font_key)
        self._sb_size_var.set(fontsize)
        self._sb_font_var.set(PDF_FONT_LABELS[self.font_index])

        cmd = InsertTextCommand(
            self.text_service, self.doc,
            self.current_page_idx, text, (pdf_x, pdf_y), fontsize,
        )
        cmd.execute()
        self._render_current_page()   # re-render so the baked text is visible

    def _on_text_cancelled(self):
        self._active_overlay = None

    def _cancel_active_overlay(self):
        if self._active_overlay:
            overlay = self._active_overlay
            self._active_overlay = None
            try:
                overlay._cancel()
            except Exception:
                pass

    # ──────────────────── Image extraction ────────────────────────────────────

    def _handle_extract_tool(self, pdf_x: float, pdf_y: float):
        page   = self.doc.get_page(self.current_page_idx)
        images = page.get_image_info()

        for img in images:
            x0, y0, x1, y1 = img['bbox']
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                xref     = img['xref']
                ext      = img.get('ext', 'png')
                out_path = filedialog.asksaveasfilename(
                    title="Save Extracted Image",
                    defaultextension=f".{ext}",
                    initialfile=f"extracted_image.{ext}",
                )
                if out_path:
                    cmd = ExtractSingleImageCommand(self.image_service, self.doc, xref, out_path)
                    cmd.execute()
                    messagebox.showinfo("Extracted", f"Image saved to:\n{out_path}")
                return

        messagebox.showinfo(
            "No Image Found",
            "No image detected at that position.\nClick directly on an image to extract it.",
        )

    # ──────────────────── Window close ────────────────────────────────────────

    def _on_closing(self):
        if self.doc:
            self.doc.close()
        self.root.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = InteractivePDFEditor(root)
    root.mainloop()