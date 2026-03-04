"""
TextBox — draggable, resizable, editable text overlay on a Tk Canvas.

Coordinate system
-----------------
All *pdf_* attributes are in PDF user-space (points, origin top-left).
The box is positioned at (pdf_x, pdf_y) which maps to canvas coords via:

    canvas_x = page_offset_x + pdf_x * scale
    canvas_y = page_offset_y + pdf_y * scale

The page offsets are injected at construction and kept up-to-date via
`rescale(scale, page_offset_x, page_offset_y)`.
"""

import tkinter as tk
from tkinter import ttk, colorchooser

from src.gui.theme import (
    PALETTE, FONT_LABEL,
    PDF_FONTS, PDF_FONT_LABELS, TK_FONT_MAP,
    GRIP_W, GRIP_H, MIN_BOX_PX,
)


class TextBox:
    """Self-contained draggable, resizable, editable text overlay on a canvas."""

    # Colours
    C_BORDER        = "#7B61FF"
    C_BORDER_HOVER  = "#A594FF"
    C_GRIP          = "#7B61FF"
    C_GRIP_HOVER    = "#FBBF24"
    C_RESIZE        = "#7B61FF"
    C_RESIZE_HOVER  = "#34D399"
    C_TOOLBAR_BG    = "#1A1A28"
    C_TOOLBAR_FG    = "#E8E8F0"
    C_ENTRY_SELECT  = "#C4B5FD"

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

        self._drag_start = None
        self._drag_mode  = None  # "move" | "resize"

        self._border_id      = None
        self._grip_id        = None
        self._grip_dots      = []
        self._resize_id      = None
        self._entry_win_id   = None
        self._toolbar_win_id = None
        self._all_ids: list  = []

        self._toolbar   = None
        self._entry     = None
        self._font_var  = tk.StringVar(value=PDF_FONT_LABELS[font_index])
        self._size_var  = tk.IntVar(value=fontsize)
        self._align_var = tk.IntVar(value=align)
        self._color_btn = None
        self._align_btns: list = []

        self._build()

    # ── geometry ──────────────────────────────────────────────────────────────

    def _cx(self) -> float:
        return self.page_offset_x + self.pdf_x * self.scale

    def _cy(self) -> float:
        return self.page_offset_y + self.pdf_y * self.scale

    def _cw(self) -> float:
        return max(MIN_BOX_PX, self.pdf_w * self.scale)

    def _ch(self) -> float:
        return max(MIN_BOX_PX * 0.5, self.pdf_h * self.scale)

    def _tk_fontsize(self) -> int:
        """Pixel-accurate font size for the Tk preview (negative = pixels)."""
        return -round(self.fontsize * self.scale)

    def _tk_font(self) -> tuple:
        family = TK_FONT_MAP.get(PDF_FONT_LABELS[self.font_index], "Helvetica")
        return (family, self._tk_fontsize())

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self):
        c = self.canvas
        cx, cy, cw, ch = self._cx(), self._cy(), self._cw(), self._ch()

        self._border_id = c.create_rectangle(
            cx, cy, cx + cw, cy + ch,
            outline=self.C_BORDER, width=2, dash=(5, 3),
        )
        self._all_ids.append(self._border_id)

        self._toolbar = tk.Frame(c, bg=self.C_TOOLBAR_BG, padx=4, pady=3)
        self._build_toolbar(self._toolbar)
        self._toolbar_win_id = c.create_window(cx, cy - 36, anchor=tk.NW, window=self._toolbar)
        self._all_ids.append(self._toolbar_win_id)

        self._entry = tk.Text(
            c,
            font=self._tk_font(),
            bg=self.entry_bg,
            fg=self._rgb_hex(self.color_rgb),
            selectbackground=self.C_ENTRY_SELECT,
            insertbackground=self.C_BORDER,
            relief="flat", bd=0, highlightthickness=0,
            wrap=tk.WORD, undo=True, padx=4, pady=2,
        )
        self._entry_win_id = c.create_window(
            cx, cy, anchor=tk.NW, window=self._entry,
            width=max(MIN_BOX_PX, cw), height=max(20, ch),
        )
        self._all_ids.append(self._entry_win_id)

        gx1, gy1 = cx - GRIP_W, cy - GRIP_H
        gx2, gy2 = cx + 2,      cy + 2
        self._grip_id = c.create_rectangle(
            gx1, gy1, gx2, gy2,
            fill=self.C_GRIP, outline="#FFFFFF", width=1,
        )
        self._all_ids.append(self._grip_id)
        self._grip_dots = self._draw_grip_dots(cx, cy)

        self._resize_id = c.create_polygon(
            0, 0, 0, 0, 0, 0,
            fill=self.C_RESIZE, outline="",
        )
        self._all_ids.append(self._resize_id)
        self._place_handles(cx, cy, cw, ch)

        for item in [self._grip_id] + self._grip_dots:
            c.tag_bind(item, "<Enter>",           self._on_grip_enter)
            c.tag_bind(item, "<Leave>",            self._on_grip_leave)
            c.tag_bind(item, "<ButtonPress-1>",    self._on_grip_press)
            c.tag_bind(item, "<B1-Motion>",        self._on_grip_drag)
            c.tag_bind(item, "<ButtonRelease-1>",  self._on_grip_release)

        c.tag_bind(self._resize_id, "<Enter>",           self._on_resize_enter)
        c.tag_bind(self._resize_id, "<Leave>",            self._on_resize_leave)
        c.tag_bind(self._resize_id, "<ButtonPress-1>",   self._on_resize_press)
        c.tag_bind(self._resize_id, "<B1-Motion>",       self._on_resize_drag)
        c.tag_bind(self._resize_id, "<ButtonRelease-1>", self._on_resize_release)

        self._entry.bind("<Control-Return>", lambda e: self._confirm())
        self._entry.bind("<Escape>",         lambda e: self._delete())
        self._entry.focus_set()
        self._set_align(self.align)

    def _build_toolbar(self, parent):
        font_cb = ttk.Combobox(
            parent, textvariable=self._font_var,
            values=PDF_FONT_LABELS, state="readonly", width=14,
        )
        font_cb.pack(side=tk.LEFT, padx=(0, 4))
        font_cb.bind("<<ComboboxSelected>>", self._on_font_change)

        size_sp = tk.Spinbox(
            parent, from_=6, to=144, textvariable=self._size_var,
            width=4, command=self._on_size_change,
            bg="#252535", fg=self.C_TOOLBAR_FG,
            buttonbackground="#2A2A3D", relief="flat", highlightthickness=0,
        )
        size_sp.pack(side=tk.LEFT, padx=(0, 4))
        size_sp.bind("<Return>", lambda e: self._on_size_change())

        self._color_btn = tk.Button(
            parent, text="  ", relief="flat", bd=1,
            bg=self._rgb_hex(self.color_rgb), width=2,
            cursor="hand2", command=self._pick_color,
            highlightthickness=1, highlightbackground="#555",
        )
        self._color_btn.pack(side=tk.LEFT, padx=(0, 6))

        align_frame = tk.Frame(parent, bg=self.C_TOOLBAR_BG)
        align_frame.pack(side=tk.LEFT, padx=(0, 8))
        self._align_btns = []
        for idx, (symbol, _tip) in enumerate([("≡L", "Left"), ("≡C", "Center"),
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

        tk.Button(
            parent, text="✓  Apply",
            bg=PALETTE["success"], fg="#0F0F13",
            font=("Helvetica", 9, "bold"), relief="flat", bd=0,
            padx=8, pady=1, cursor="hand2", command=self._confirm,
        ).pack(side=tk.LEFT, padx=(0, 4))

        tk.Button(
            parent, text="✕",
            bg=PALETTE["danger"], fg="#0F0F13",
            font=("Helvetica", 9, "bold"), relief="flat", bd=0,
            padx=6, pady=1, cursor="hand2", command=self._delete,
        ).pack(side=tk.LEFT)

    def _draw_grip_dots(self, cx: float, cy: float) -> list:
        c    = self.canvas
        ids  = []
        cols, rows, dot, pad = 3, 2, 2, 3
        ox = cx - GRIP_W + pad
        oy = cy - GRIP_H + pad
        sx = (GRIP_W - pad * 2 - dot * cols) / max(cols - 1, 1)
        sy = (GRIP_H - pad * 2 - dot * rows) / max(rows - 1, 1)
        for r in range(rows):
            for col in range(cols):
                x1 = ox + col * (dot + sx)
                y1 = oy + r   * (dot + sy)
                did = c.create_rectangle(x1, y1, x1 + dot, y1 + dot, fill="#FFFFFF", outline="")
                ids.append(did)
                self._all_ids.append(did)
        return ids

    def _place_handles(self, cx: float, cy: float, cw: float, ch: float):
        c = self.canvas
        gx1, gy1 = cx - GRIP_W, cy - GRIP_H
        gx2, gy2 = cx + 2,      cy + 2
        c.coords(self._grip_id, gx1, gy1, gx2, gy2)

        dot, pad = 2, 3
        ox = cx - GRIP_W + pad
        oy = cy - GRIP_H + pad
        cols, rows = 3, 2
        sx = (GRIP_W - pad * 2 - dot * cols) / max(cols - 1, 1)
        sy = (GRIP_H - pad * 2 - dot * rows) / max(rows - 1, 1)
        for i, did in enumerate(self._grip_dots):
            r   = i // cols
            col = i %  cols
            x1  = ox + col * (dot + sx)
            y1  = oy + r   * (dot + sy)
            c.coords(did, x1, y1, x1 + dot, y1 + dot)

        ts = 16
        rx, ry = cx + cw, cy + ch
        c.coords(self._resize_id, rx, ry - ts, rx, ry, rx - ts, ry)

    # ── rescale ───────────────────────────────────────────────────────────────

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
        c.itemconfigure(self._entry_win_id, width=max(MIN_BOX_PX, cw), height=max(20, ch))
        self._entry.config(font=self._tk_font())
        self._place_handles(cx, cy, cw, ch)

    # ── grip (move) ───────────────────────────────────────────────────────────

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
        return "break"

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

    # ── resize ────────────────────────────────────────────────────────────────

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
        return "break"

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

    # ── options ───────────────────────────────────────────────────────────────

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
        self.align = align
        self._align_var.set(align)
        self._refresh_align_buttons()
        tk_justify = ["left", "center", "right", "left"][align]
        self._entry.tag_configure("all", justify=tk_justify)
        self._entry.tag_add("all", "1.0", tk.END)

    def _refresh_align_buttons(self):
        for i, btn in enumerate(self._align_btns):
            if i == self.align:
                btn.config(bg=PALETTE["accent"], fg="#FFFFFF")
            else:
                btn.config(bg="#2A2A3D", fg=self.C_TOOLBAR_FG)

    def _pick_color(self):
        result = colorchooser.askcolor(color=self._rgb_hex(self.color_rgb), title="Text Color")
        if result and result[0]:
            self.color_rgb = tuple(int(v) for v in result[0])
            self._color_btn.config(bg=self._rgb_hex(self.color_rgb))
            self._entry.config(fg=self._rgb_hex(self.color_rgb))

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
        self._grip_dots = []

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