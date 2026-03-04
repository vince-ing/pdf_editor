# src/gui/widgets/text_box.py

"""
TextBox — draggable, auto-resizing, editable text overlay on a Tk Canvas.

Coordinate system
-----------------
All *pdf_* attributes are in PDF user-space (points, origin top-left).
The box is positioned at (pdf_x, pdf_y) which maps to canvas coords via:

    canvas_x = page_offset_x + pdf_x * scale
    canvas_y = page_offset_y + pdf_y * scale
"""

import tkinter as tk
from tkinter import font as tkfont

from src.gui.theme import (
    PALETTE, PDF_FONTS, PDF_FONT_LABELS, TK_FONT_MAP,
    MIN_BOX_PX
)


class TextBox:
    """Self-contained draggable, auto-resizing text overlay on a canvas."""

    C_BORDER     = "#3B82F6"  # Blue stroke
    C_TOOLBAR_BG = "#1A1A28"

    def __init__(
        self,
        canvas: tk.Canvas,
        pdf_x: float, pdf_y: float,
        pdf_w: float, pdf_h: float,
        scale: float,
        page_offset_x: float,
        page_offset_y: float,
        font_index: int  = 0,
        fontsize: int    = 14,
        color_rgb: tuple = (0, 0, 0),
        entry_bg: str    = "#FFFFFF",
        align: int       = 0,
        on_commit=None,
        on_delete=None,
        on_interact=None,
    ):
        self.canvas        = canvas
        self.pdf_x         = pdf_x
        self.pdf_y         = pdf_y
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

        # Dynamically sized as the user types
        self.pdf_w         = pdf_w
        self.pdf_h         = pdf_h

        self._drag_start = None

        self._border_id      = None
        self._hitbox_id      = None
        self._entry_win_id   = None
        self._toolbar_win_id = None
        self._all_ids: list  = []

        self._toolbar   = None
        self._entry     = None

        self._build()

    # ── geometry ──────────────────────────────────────────────────────────────

    def _cx(self) -> float:
        return self.page_offset_x + self.pdf_x * self.scale

    def _cy(self) -> float:
        return self.page_offset_y + self.pdf_y * self.scale

    def _tk_fontsize(self) -> int:
        """Pixel-accurate font size for the Tk preview (negative = pixels)."""
        return -round(self.fontsize * self.scale)

    def _tk_font(self) -> tuple:
        family = TK_FONT_MAP.get(PDF_FONT_LABELS[self.font_index], "Helvetica")
        return (family, self._tk_fontsize())

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        c = self.canvas
        cx, cy = self._cx(), self._cy()

        # Invisible padded hitbox to make grabbing the border easy
        self._hitbox_id = c.create_rectangle(
            cx - 10, cy - 10, cx + 50, cy + 30,
            fill="", outline="", tags="textbox_drag"
        )
        self._all_ids.append(self._hitbox_id)

        # Rounded blue border
        self._border_id = c.create_polygon(
            0, 0, 0, 0,
            fill="", outline=self.C_BORDER, width=2, smooth=True, tags="textbox_drag"
        )
        self._all_ids.append(self._border_id)

        # Mini confirmation toolbar
        self._toolbar = tk.Frame(c, bg=self.C_TOOLBAR_BG, padx=2, pady=2, bd=0)
        
        tk.Button(
            self._toolbar, text="✓", fg="#0F0F13", bg=PALETTE["success"],
            font=("Helvetica", 10, "bold"), relief="flat", bd=0,
            padx=4, pady=0, cursor="hand2", command=self._confirm
        ).pack(side=tk.LEFT, padx=1)
        
        tk.Button(
            self._toolbar, text="✕", fg="#0F0F13", bg=PALETTE["danger"],
            font=("Helvetica", 10, "bold"), relief="flat", bd=0,
            padx=4, pady=0, cursor="hand2", command=self._delete
        ).pack(side=tk.LEFT, padx=1)

        # The toolbar is hidden until focused/clicked
        self._toolbar_win_id = c.create_window(
            cx, cy - 25, anchor=tk.SW, window=self._toolbar, state=tk.HIDDEN
        )
        self._all_ids.append(self._toolbar_win_id)

        # WYSIWYG text entry: absolutely zero padding or borders
        self._entry = tk.Text(
            c,
            font=self._tk_font(),
            bg=self.entry_bg,
            fg=self._rgb_hex(self.color_rgb),
            selectbackground="#C4B5FD",
            insertbackground=self.C_BORDER,
            relief="flat", bd=0, highlightthickness=0,
            padx=0, pady=0,
            wrap=tk.WORD, undo=True
        )
        
        tk_justify = ["left", "center", "right", "left"][self.align]
        self._entry.tag_configure("all", justify=tk_justify)

        self._entry_win_id = c.create_window(
            cx, cy, anchor=tk.NW, window=self._entry,
            width=MIN_BOX_PX, height=20
        )
        self._all_ids.append(self._entry_win_id)

        # Drag bindings
        c.tag_bind("textbox_drag", "<Enter>", lambda e: c.config(cursor="fleur"))
        c.tag_bind("textbox_drag", "<Leave>", lambda e: c.config(cursor="crosshair"))
        c.tag_bind("textbox_drag", "<ButtonPress-1>", self._on_drag_press)
        c.tag_bind("textbox_drag", "<B1-Motion>", self._on_drag_motion)
        c.tag_bind("textbox_drag", "<ButtonRelease-1>", self._on_drag_release)

        # Typing bindings
        self._entry.bind("<KeyRelease>", self._on_key_release)
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<Control-Return>", lambda e: self._confirm())
        self._entry.bind("<Escape>", lambda e: self._delete())
        
        self._entry.focus_set()
        self._update_size()

    # ── dynamic sizing ────────────────────────────────────────────────────────

    def _on_focus_in(self, event=None):
        self.canvas.itemconfigure(self._toolbar_win_id, state=tk.NORMAL)
        
    def _on_key_release(self, event=None):
        self._entry.tag_add("all", "1.0", tk.END)
        self._update_size()

    def _update_size(self):
        """Dynamically measure the exact pixel dimensions of the text to hug it tightly."""
        text = self.get_text()
        if not text:
            text = " "  # Ensure a minimum height exists
            
        lines = text.split("\n")
        f = tkfont.Font(font=self._tk_font())
        
        # Calculate precise width and height
        max_w = max([f.measure(line) for line in lines] + [MIN_BOX_PX]) + 2
        line_h = f.metrics("linespace")
        total_h = line_h * len(lines)

        # Update the Tkinter window containing the text
        self.canvas.itemconfigure(self._entry_win_id, width=max_w, height=total_h)
        
        # Update the underlying PDF dimensions so the inserted text matches exactly
        self.pdf_w = max_w / self.scale
        self.pdf_h = total_h / self.scale
        
        cx, cy = self._cx(), self._cy()
        
        # Create coordinates for a smooth rounded rectangle
        r = 6
        x1, y1 = cx - 4, cy - 2
        x2, y2 = cx + max_w + 4, cy + total_h + 2
        
        points = [
            x1+r, y1,
            x2-r, y1, x2, y1, x2, y1+r,
            x2, y2-r, x2, y2, x2-r, y2,
            x1+r, y2, x1, y2, x1, y2-r,
            x1, y1+r, x1, y1, x1+r, y1
        ]
        self.canvas.coords(self._border_id, points)
        
        # Update the invisible drag hitbox
        self.canvas.coords(self._hitbox_id, x1-10, y1-10, x2+10, y2+10)
        
        # Keep the mini toolbar attached to the top right
        self.canvas.coords(self._toolbar_win_id, x2, y1 - 4)
        self.canvas.itemconfigure(self._toolbar_win_id, anchor=tk.SE)

    # ── rescale ───────────────────────────────────────────────────────────────

    def rescale(self, scale: float, page_offset_x: float, page_offset_y: float):
        self.scale         = scale
        self.page_offset_x = page_offset_x
        self.page_offset_y = page_offset_y
        self._reposition()

    def _reposition(self):
        cx, cy = self._cx(), self._cy()
        self.canvas.coords(self._entry_win_id, cx, cy)
        self._entry.config(font=self._tk_font())
        self._update_size()

    # ── drag controls ─────────────────────────────────────────────────────────

    def _on_drag_press(self, event):
        self._drag_start = (event.x_root, event.y_root)
        if self.on_interact:
            self.on_interact()
        # Hide toolbar while dragging to prevent stutter
        self.canvas.itemconfigure(self._toolbar_win_id, state=tk.HIDDEN)
        return "break"

    def _on_drag_motion(self, event):
        if not self._drag_start:
            return
        dx = (event.x_root - self._drag_start[0]) / self.scale
        dy = (event.y_root - self._drag_start[1]) / self.scale
        self._drag_start = (event.x_root, event.y_root)
        self.pdf_x += dx
        self.pdf_y += dy
        self._reposition()

    def _on_drag_release(self, _e):
        self._drag_start = None
        self.canvas.itemconfigure(self._toolbar_win_id, state=tk.NORMAL)
        self._entry.focus_set()

    # ── confirm / delete ──────────────────────────────────────────────────────

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
    
    def update_style(self, font_index: int, fontsize: int, color_rgb: tuple, align: int):
        """Called by the main window to live-update the box when sidebar properties change."""
        self.font_index = font_index
        self.fontsize   = fontsize
        self.color_rgb  = color_rgb
        self.align      = align
        
        self._entry.config(
            font=self._tk_font(),
            fg=self._rgb_hex(self.color_rgb)
        )
        tk_justify = ["left", "center", "right", "left"][self.align]
        self._entry.tag_configure("all", justify=tk_justify)
        self._entry.tag_add("all", "1.0", tk.END)
        self._update_size()

    # ── helpers ───────────────────────────────────────────────────────────────

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