"""
ThumbnailPanel — lazy-rendered page thumbnail strip.

Renders page previews in the background via after_idle() so the UI stays
responsive while opening large PDFs.  Each slot starts as a placeholder
rectangle and is filled as pages are visited or scheduled.
"""

import tkinter as tk
from tkinter import ttk

from src.gui.theme import (
    PALETTE, FONT_LABEL,
    THUMB_SCALE, THUMB_PAD, THUMB_PANEL_W,
)


class ThumbnailPanel:
    """
    Right-hand panel showing one thumbnail per page.

    Parameters
    ----------
    parent : tk.Widget
        The frame to pack this panel into.
    get_doc : callable
        Returns the current PDFDocument (or None).
    get_current_page : callable
        Returns the current 0-based page index.
    on_page_click : callable
        Called with the clicked page index when a thumbnail is clicked.
    root : tk.Tk
        The root window, used for after() / after_idle() scheduling.
    """

    def __init__(self, parent, get_doc, get_current_page, on_page_click, root):
        self._get_doc          = get_doc
        self._get_current_page = get_current_page
        self._on_page_click    = on_page_click
        self._root             = root

        self._images: list        = []   # tk.PhotoImage references (keep alive)
        self._dirty: list[bool]   = []
        self._after_id            = None

        self._frame = tk.Frame(
            parent,
            bg=PALETTE["bg_panel"],
            width=THUMB_PANEL_W,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        self._frame.pack(side=tk.RIGHT, fill=tk.Y)
        self._frame.pack_propagate(False)

        hdr = tk.Frame(self._frame, bg=PALETTE["bg_mid"], height=26)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)
        tk.Label(
            hdr, text="PAGES",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            font=("Helvetica", 8, "bold"), padx=10,
        ).pack(side=tk.LEFT, fill=tk.Y)

        scroll_frame = tk.Frame(self._frame, bg=PALETTE["bg_panel"])
        scroll_frame.pack(fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(scroll_frame, orient=tk.VERTICAL)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self._canvas = tk.Canvas(
            scroll_frame,
            bg=PALETTE["bg_panel"],
            highlightthickness=0,
            yscrollcommand=vsb.set,
        )
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.config(command=self._canvas.yview)

        self._canvas.bind("<MouseWheel>", self._on_scroll)
        self._canvas.bind("<Button-4>",   self._on_scroll)
        self._canvas.bind("<Button-5>",   self._on_scroll)

    # ── public interface ──────────────────────────────────────────────────────

    def show(self):
        self._frame.pack(side=tk.RIGHT, fill=tk.Y)
        self._root.after(50, self.scroll_to_active)

    def hide(self):
        self._frame.pack_forget()

    def reset(self):
        """
        Called when a new document is loaded or the page count changes.
        Clears caches, rebuilds placeholder slots, and schedules lazy rendering.
        """
        if self._after_id:
            self._root.after_cancel(self._after_id)
            self._after_id = None

        self._canvas.delete("all")
        self._images = []
        self._dirty  = []

        doc = self._get_doc()
        if not doc:
            return

        n = doc.page_count
        self._images = [None] * n
        self._dirty  = [True]  * n

        p0  = doc.get_page(0)
        tw  = int(p0.width  * THUMB_SCALE)
        th  = int(p0.height * THUMB_SCALE)
        x_off = (THUMB_PANEL_W - tw) // 2

        total_h = (th + THUMB_PAD + 18) * n + THUMB_PAD
        self._canvas.config(scrollregion=(0, 0, THUMB_PANEL_W, total_h))

        for i in range(n):
            y_top = THUMB_PAD + i * (th + THUMB_PAD + 18)

            # Placeholder: transparent fill so the image shows through once rendered.
            # A solid fill here would cover the image after tag_raise reorders items.
            self._canvas.create_rectangle(
                x_off, y_top, x_off + tw, y_top + th,
                fill="",                      # <-- transparent, not bg_hover
                outline=PALETTE["border"],
                width=1,
                tags=(f"thumb_border_{i}",),
            )
            self._canvas.create_text(
                THUMB_PANEL_W // 2, y_top + th + 6,
                text=str(i + 1),
                fill=PALETTE["fg_dim"],
                font=("Helvetica", 7),
                tags=(f"thumb_label_{i}",),
            )
            # Invisible hit-target rectangle on top of everything for click/hover
            self._canvas.create_rectangle(
                x_off, y_top, x_off + tw, y_top + th,
                fill="", outline="",
                tags=(f"thumb_hit_{i}",),
            )
            self._canvas.tag_bind(
                f"thumb_hit_{i}", "<Button-1>",
                lambda e, idx=i: self._on_page_click(idx),
            )
            self._canvas.tag_bind(
                f"thumb_hit_{i}", "<Enter>",
                lambda e, idx=i: self._on_hover(idx, True),
            )
            self._canvas.tag_bind(
                f"thumb_hit_{i}", "<Leave>",
                lambda e, idx=i: self._on_hover(idx, False),
            )

        self._schedule_render(priority_page=self._get_current_page())

    def mark_dirty(self, page_idx=None):
        """
        Mark one page (or all pages when page_idx is None) for re-render,
        then schedule a lazy pass.
        """
        if not self._dirty:
            return
        if page_idx is None:
            self._dirty = [True] * len(self._dirty)
        elif 0 <= page_idx < len(self._dirty):
            self._dirty[page_idx] = True
        self._schedule_render(priority_page=self._get_current_page())

    def refresh_all_borders(self):
        """Repaint every border — call after the active page changes."""
        doc = self._get_doc()
        if not doc:
            return
        for i in range(doc.page_count):
            self._update_border(i)

    def scroll_to_active(self):
        """Scroll so the active thumbnail is visible."""
        doc = self._get_doc()
        if not doc:
            return
        n    = doc.page_count
        frac = self._get_current_page() / max(n, 1)
        self._canvas.yview_moveto(max(0.0, frac - 0.1))

    # ── internals ─────────────────────────────────────────────────────────────

    def _geometry(self, page_idx: int) -> tuple:
        """Return (tw, th, x_off, y_top) for the given page slot."""
        doc = self._get_doc()
        p   = doc.get_page(page_idx)
        tw  = int(p.width  * THUMB_SCALE)
        th  = int(p.height * THUMB_SCALE)
        x_off = (THUMB_PANEL_W - tw) // 2
        y_top = THUMB_PAD + page_idx * (th + THUMB_PAD + 18)
        return tw, th, x_off, y_top

    def _schedule_render(self, priority_page: int = 0):
        doc = self._get_doc()
        if not doc:
            return
        n     = doc.page_count
        order = [priority_page] + [i for i in range(n) if i != priority_page]

        def _render_one(remaining):
            if not remaining or not self._get_doc():
                self._after_id = None
                return
            idx  = remaining[0]
            rest = remaining[1:]
            if 0 <= idx < len(self._dirty) and self._dirty[idx]:
                self._render_page(idx)
            self._after_id = self._root.after_idle(lambda: _render_one(rest))

        _render_one(order)

    def _render_page(self, idx: int):
        doc = self._get_doc()
        if not doc or idx >= doc.page_count:
            return
        try:
            page = doc.get_page(idx)
            ppm  = page.render_to_ppm(scale=THUMB_SCALE)
            img  = tk.PhotoImage(data=ppm)
        except Exception:
            return

        self._images[idx] = img
        self._dirty[idx]  = False

        tw, th, x_off, y_top = self._geometry(idx)

        # Remove old image item if re-rendering a dirty page
        self._canvas.delete(f"thumb_img_{idx}")

        # Draw the image
        self._canvas.create_image(
            x_off, y_top, anchor=tk.NW, image=img,
            tags=(f"thumb_img_{idx}",),
        )

        # Stack order (bottom → top): image → border → label → hit-target
        # border has transparent fill so the image shows through it;
        # hit-target is invisible but must stay on top to receive events.
        self._canvas.tag_raise(f"thumb_border_{idx}")
        self._canvas.tag_raise(f"thumb_label_{idx}")
        self._canvas.tag_raise(f"thumb_hit_{idx}")

        self._update_border(idx)

    def _update_border(self, idx: int):
        is_active = (idx == self._get_current_page())
        color = PALETTE["accent"] if is_active else PALETTE["border"]
        width = 2 if is_active else 1
        self._canvas.itemconfig(f"thumb_border_{idx}", outline=color, width=width)
        self._canvas.itemconfig(
            f"thumb_label_{idx}",
            fill=PALETTE["fg_primary"] if is_active else PALETTE["fg_dim"],
        )

    def _on_hover(self, idx: int, entering: bool):
        if idx == self._get_current_page():
            return
        color = PALETTE["accent_light"] if entering else PALETTE["border"]
        width = 2 if entering else 1
        self._canvas.itemconfig(f"thumb_border_{idx}", outline=color, width=width)

    def _on_scroll(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        elif hasattr(event, "delta"):
            self._canvas.yview_scroll(-1 * (event.delta // 120), "units")