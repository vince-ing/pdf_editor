"""
ThumbnailPanel — lazy-rendered page thumbnail strip with full page management.

Features
--------
• Active Viewport Caching: Only renders visible pages ± buffer, evicting others to save RAM.
• Lazy background rendering via after_idle so the UI stays responsive.
• Drag-to-reorder: grab any thumbnail and drag it to a new position.
• Hover delete button: a small ✕ badge appears in the top-right corner.
"""

import tkinter as tk
from tkinter import ttk

from src.gui.theme import (
    PALETTE, FONT_LABEL,
    THUMB_SCALE, THUMB_PAD, THUMB_PANEL_W,
)

# How many pixels the mouse must move before we start a drag
_DRAG_THRESHOLD = 6


class ThumbnailPanel:
    def __init__(
        self,
        parent,
        get_doc,
        get_current_page,
        on_page_click,
        root,
        on_reorder=None,
        on_add_page=None,
        on_delete_page=None,
        on_duplicate_page=None,
        on_rotate_page=None,
        get_image_thumbnail=None,
    ):
        self._get_doc              = get_doc
        self._get_current_page     = get_current_page
        self._on_page_click_cb     = on_page_click
        self._root               = root
        self._on_reorder         = on_reorder
        self._on_add_page        = on_add_page
        self._on_delete_page     = on_delete_page
        self._on_duplicate_page  = on_duplicate_page
        self._on_rotate_page     = on_rotate_page
        self._get_image_thumbnail = get_image_thumbnail 
        self._is_image_mode = False                     
        self._image_paths: list[str] = []

        self._images: list       = []
        self._dirty: list[bool]  = []
        self._after_id           = None

        # Drag state
        self._drag_src: int | None    = None
        self._drag_ghost: int | None  = None
        self._drag_line: int | None   = None
        self._drag_started            = False
        self._drag_press_y: float     = 0.0
        self._drag_press_x: float     = 0.0

        # Hover state
        self._hover_idx: int | None   = None
        self._del_btn_id: int | None  = None

        # Build widgets
        self._frame = tk.Frame(
            parent,
            bg=PALETTE["bg_panel"],
            width=THUMB_PANEL_W,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        self._frame.pack(side=tk.RIGHT, fill=tk.Y)
        self._frame.pack_propagate(False)

        self._build_header()

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
        
        # Intercept scrollbar movements to trigger caching updates
        def _yview_wrapper(*args):
            self._canvas.yview(*args)
            self._on_view_changed()
            
        vsb.config(command=_yview_wrapper)

        self._canvas.bind("<MouseWheel>",      self._on_scroll)
        self._canvas.bind("<Button-4>",        self._on_scroll)
        self._canvas.bind("<Button-5>",        self._on_scroll)
        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",       self._on_motion)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._canvas.bind("<Button-3>",        self._on_right_click)
        self._canvas.bind("<Motion>",          self._on_hover_motion)
        self._canvas.bind("<Leave>",           self._on_canvas_leave)

    def _build_header(self):
        hdr = tk.Frame(self._frame, bg=PALETTE["bg_mid"], height=26)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        tk.Label(
            hdr, text="PAGES",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            font=("Helvetica", 8, "bold"), padx=10,
        ).pack(side=tk.LEFT, fill=tk.Y)

        add_btn = tk.Button(
            hdr, text="+",
            bg=PALETTE["bg_mid"], fg=PALETTE["accent_light"],
            activebackground=PALETTE["bg_hover"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica", 13, "bold"),
            relief="flat", bd=0, padx=8, pady=0,
            cursor="hand2",
            command=self._on_add_at_end,
        )
        add_btn.pack(side=tk.RIGHT, fill=tk.Y)

    def show(self):
        self._frame.pack(side=tk.RIGHT, fill=tk.Y)
        self._root.after(50, self.scroll_to_active)

    def hide(self):
        self._frame.pack_forget()
    
    def reset_for_images(self, image_paths: list[str]):
        if self._after_id:
            self._root.after_cancel(self._after_id)
            self._after_id = None

        self._canvas.delete("all")
        self._is_image_mode = True
        self._image_paths = list(image_paths)
        self._images = [None] * len(self._image_paths)
        self._dirty = [True] * len(self._image_paths)
        
        self._slot_tw, self._slot_th = 80, 110
        tw, th = self._thumb_size()
        x_off = (THUMB_PANEL_W - tw) // 2
        
        total_h = self._slot_h() * len(self._image_paths) + THUMB_PAD
        self._canvas.config(scrollregion=(0, 0, THUMB_PANEL_W, total_h))

        for i in range(len(self._image_paths)):
            self._create_slot(i, x_off, tw, th)
        
        self._schedule_render()

    def reset(self):
        self._is_image_mode = False
        if self._after_id:
            self._root.after_cancel(self._after_id)
            self._after_id = None

        self._canvas.delete("all")
        self._images     = []
        self._dirty      = []
        self._hover_idx  = None
        self._del_btn_id = None

        doc = self._get_doc()
        if not doc:
            return

        try:
            p = doc.get_page(0)
            tw = int(p.width * THUMB_SCALE)
            th = int(p.height * THUMB_SCALE)
            self._slot_tw = min(tw, th)
            self._slot_th = max(tw, th)
        except Exception:
            self._slot_tw, self._slot_th = 80, 110

        n     = doc.page_count
        self._images = [None] * n
        self._dirty  = [True]  * n

        tw, th = self._thumb_size()
        x_off  = (THUMB_PANEL_W - tw) // 2

        total_h = self._slot_h() * n + THUMB_PAD
        self._canvas.config(scrollregion=(0, 0, THUMB_PANEL_W, total_h))

        for i in range(n):
            self._create_slot(i, x_off, tw, th)

        self._schedule_render(priority_page=self._get_current_page())

    def mark_dirty(self, page_idx=None):
        if not self._dirty:
            return
        if page_idx is None:
            self._dirty = [True] * len(self._dirty)
        elif 0 <= page_idx < len(self._dirty):
            self._dirty[page_idx] = True
        self._schedule_render(priority_page=self._get_current_page())

    def refresh_all_borders(self):
        doc = self._get_doc()
        if not doc:
            return
        for i in range(doc.page_count):
            self._update_border(i)

    def scroll_to_active(self):
        doc = self._get_doc()
        if not doc and not self._is_image_mode:
            return
            
        n = doc.page_count if doc else len(self._image_paths)
        if n == 0: 
            return
            
        # Get actual pixel height of the total scrollable region
        total_h = self._slot_h() * n + THUMB_PAD
        if total_h <= 0:
            return
            
        # Get the exact pixel Y coordinate of the active thumbnail
        target_y = self._slot_y(self._get_current_page())
        
        # Offset the target Y up by 1.5 thumbnail slots.
        # This perfectly places the active page near the top of the view
        # while still letting you see the preceding page above it.
        offset_y = target_y - (self._slot_h() * 1.5)
        
        # Convert the pixel position into a fraction (0.0 to 1.0) for Tkinter
        frac = offset_y / total_h
        
        # Clamp it so we don't accidentally try to scroll past the boundaries
        frac = max(0.0, min(1.0, frac))
        
        self._canvas.yview_moveto(frac)
        self._on_view_changed()

    def _thumb_size(self) -> tuple[int, int]:
        if hasattr(self, "_slot_tw") and hasattr(self, "_slot_th"):
            return self._slot_tw, self._slot_th
        return 80, 110

    def _slot_h(self) -> int:
        _, th = self._thumb_size()
        return th + THUMB_PAD + 18

    def _slot_y(self, idx: int) -> int:
        return THUMB_PAD + idx * self._slot_h()

    def _y_to_drop_idx(self, canvas_y: float) -> int:
        doc = self._get_doc()
        n   = doc.page_count if doc else 0
        sh  = self._slot_h()
        idx = int((canvas_y - THUMB_PAD // 2) / sh + 0.5)
        return max(0, min(n, idx))

    def _y_to_page_idx(self, canvas_y: float) -> int | None:
        doc = self._get_doc()
        if not doc:
            return None
        _, th = self._thumb_size()
        sh    = self._slot_h()
        idx   = int((canvas_y - THUMB_PAD) / sh)
        if idx < 0 or idx >= doc.page_count:
            return None
        y_top = self._slot_y(idx)
        if canvas_y < y_top or canvas_y > y_top + th:
            return None
        return idx

    def _create_slot(self, i: int, x_off: int, tw: int, th: int):
        y_top = self._slot_y(i)
        self._canvas.create_rectangle(
            x_off, y_top, x_off + tw, y_top + th,
            fill="", outline=PALETTE["border"], width=1,
            tags=(f"thumb_border_{i}",),
        )
        self._canvas.create_text(
            THUMB_PANEL_W // 2, y_top + th + 6,
            text=str(i + 1), fill=PALETTE["fg_dim"],
            font=("Helvetica", 7), tags=(f"thumb_label_{i}",),
        )
        self._canvas.create_rectangle(
            x_off, y_top, x_off + tw, y_top + th,
            fill="", outline="", tags=(f"thumb_hit_{i}",),
        )

    # ── Memory Caching & Rendering ────────────────────────────────────────────

    def _on_view_changed(self):
        """Called whenever the canvas is scrolled to evict old pages and render new ones."""
        self._schedule_render(priority_page=self._get_current_page())

    def _schedule_render(self, priority_page: int = 0):
        if self._after_id:
            self._root.after_cancel(self._after_id)
            self._after_id = None

        doc = self._get_doc()
        n = doc.page_count if doc else (len(self._image_paths) if self._is_image_mode else 0)
        if n == 0:
            return

        # 1. Calculate strictly what is visible right now
        top_frac, bottom_frac = self._canvas.yview()
        start_idx = max(0, int(top_frac * n))
        end_idx = min(n - 1, int(bottom_frac * n))
        
        # 2. Keep a safe buffer so scrolling isn't completely blank
        BUFFER = 5
        start_idx = max(0, start_idx - BUFFER)
        end_idx = min(n - 1, end_idx + BUFFER)

        # 3. GARBAGE COLLECTION: Evict anything outside the safe buffer zone
        for i in range(n):
            if i < start_idx or i > end_idx:
                if i < len(self._images) and self._images[i] is not None:
                    self._images[i] = None   # Drops reference to free RAM instantly
                    self._dirty[i] = True
                    self._canvas.delete(f"thumb_img_{i}")

        # 4. Schedule only the visible zone to be rendered
        order = []
        if start_idx <= priority_page <= end_idx and priority_page < len(self._dirty) and self._dirty[priority_page]:
            order.append(priority_page)
            
        for i in range(start_idx, end_idx + 1):
            if i != priority_page and i < len(self._dirty) and self._dirty[i]:
                order.append(i)

        def _render_one(remaining):
            if not remaining:
                self._after_id = None
                return
            if not self._is_image_mode and not self._get_doc():
                self._after_id = None
                return
            
            idx  = remaining[0]
            rest = remaining[1:]
            if 0 <= idx < len(self._dirty) and self._dirty[idx]:
                self._render_page(idx)
            self._after_id = self._root.after_idle(lambda: _render_one(rest))

        _render_one(order)

    def _render_page(self, idx: int):
        if self._is_image_mode:
            if not self._get_image_thumbnail or idx >= len(self._image_paths):
                return
            path = self._image_paths[idx]
            tw, th = self._thumb_size()
            ppm = self._get_image_thumbnail(path, tw)
            if not ppm: return
            img = tk.PhotoImage(data=ppm)
            self._images[idx] = img
            self._dirty[idx] = False
            
            x_off = (THUMB_PANEL_W - tw) // 2
            y_top = self._slot_y(idx)

            actual_w, actual_h = img.width(), img.height()
            img_x = x_off + (tw - actual_w) // 2
            img_y = y_top + (th - actual_h) // 2

            self._canvas.delete(f"thumb_img_{idx}")
            self._canvas.create_image(img_x, img_y, anchor=tk.NW, image=img, tags=(f"thumb_img_{idx}",))
            self._canvas.coords(f"thumb_border_{idx}", img_x, img_y, img_x + actual_w, img_y + actual_h)
            self._canvas.coords(f"thumb_hit_{idx}", img_x, img_y, img_x + actual_w, img_y + actual_h)
            self._canvas.tag_raise(f"thumb_border_{idx}")
            self._canvas.tag_raise(f"thumb_label_{idx}")
            self._canvas.tag_raise(f"thumb_hit_{idx}")
            self._update_border(idx)
            return
        
        doc = self._get_doc()
        if not doc or idx >= doc.page_count:
            return

        tw, th = self._thumb_size()
        x_off  = (THUMB_PANEL_W - tw) // 2
        y_top  = self._slot_y(idx)

        try:
            page = doc.get_page(idx)
            ppm = page.render_to_ppm(scale=THUMB_SCALE)
            temp_img = tk.PhotoImage(data=ppm)
            actual_w, actual_h = temp_img.width(), temp_img.height()
            
            if actual_w > tw or actual_h > th:
                scale_correction = min(tw / actual_w, th / actual_h) * 0.98
                corrected_scale = THUMB_SCALE * scale_correction
                ppm = page.render_to_ppm(scale=corrected_scale)
                img = tk.PhotoImage(data=ppm)
                actual_w, actual_h = img.width(), img.height()
            else:
                img = temp_img
        except Exception:
            return

        self._images[idx] = img
        self._dirty[idx]  = False

        img_x = x_off + (tw - actual_w) // 2
        img_y = y_top + (th - actual_h) // 2

        self._canvas.delete(f"thumb_img_{idx}")
        self._canvas.create_image(img_x, img_y, anchor=tk.NW, image=img, tags=(f"thumb_img_{idx}",))
        self._canvas.coords(f"thumb_border_{idx}", img_x, img_y, img_x + actual_w, img_y + actual_h)
        self._canvas.coords(f"thumb_hit_{idx}", img_x, img_y, img_x + actual_w, img_y + actual_h)
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

    # ── interactions ──────────────────────────────────────────────────────────

    def _on_press(self, event):
        cy = self._canvas.canvasy(event.y)
        cx = self._canvas.canvasx(event.x)
        idx = self._y_to_page_idx(cy)
        if idx is None: return
        self._drag_src      = idx
        self._drag_started  = False
        self._drag_press_y  = cy
        self._drag_press_x  = cx

    def _on_motion(self, event):
        cy = self._canvas.canvasy(event.y)
        if self._drag_src is None: return

        if not self._drag_started:
            if abs(cy - self._drag_press_y) < _DRAG_THRESHOLD: return
            self._drag_started = True
            self._hide_del_badge()

        tw, th = self._thumb_size()
        x_off  = (THUMB_PANEL_W - tw) // 2

        gx0, gy0 = x_off,      cy - th // 2
        gx1, gy1 = x_off + tw, cy + th // 2
        if self._drag_ghost is None:
            self._drag_ghost = self._canvas.create_rectangle(
                gx0, gy0, gx1, gy1,
                fill=PALETTE["accent_dim"], outline=PALETTE["accent_light"],
                width=2, stipple="gray50", tags="drag_ghost",
            )
            self._canvas.create_text(
                THUMB_PANEL_W // 2, (gy0 + gy1) // 2,
                text=str(self._drag_src + 1), fill=PALETTE["accent_light"],
                font=("Helvetica", 9, "bold"), tags="drag_ghost",
            )
        else:
            self._canvas.coords(self._drag_ghost, gx0, gy0, gx1, gy1)
            items = self._canvas.find_withtag("drag_ghost")
            if len(items) >= 2:
                self._canvas.coords(items[1], THUMB_PANEL_W // 2, (gy0 + gy1) // 2)

        drop_idx = self._y_to_drop_idx(cy)
        line_y   = self._slot_y(drop_idx) if drop_idx < (self._get_doc().page_count if self._get_doc() else 0) \
                   else self._slot_y(drop_idx - 1) + self._slot_h() - THUMB_PAD

        if self._drag_line is None:
            self._drag_line = self._canvas.create_line(
                x_off - 4, line_y, x_off + tw + 4, line_y,
                fill=PALETTE["accent"], width=3, tags="drag_line",
            )
        else:
            self._canvas.coords(self._drag_line, x_off - 4, line_y, x_off + tw + 4, line_y)

        self._canvas.tag_raise("drag_ghost")
        self._canvas.tag_raise("drag_line")

    def _on_release(self, event):
        cy = self._canvas.canvasy(event.y)
        if self._drag_ghost is not None:
            self._canvas.delete("drag_ghost")
            self._drag_ghost = None
        if self._drag_line is not None:
            self._canvas.delete("drag_line")
            self._drag_line = None

        src = self._drag_src
        self._drag_src     = None
        started            = self._drag_started
        self._drag_started = False

        if src is None: return
        if not started:
            self._on_page_click_cb(src)
            return

        doc = self._get_doc()
        if not doc: return

        dst = self._y_to_drop_idx(cy)
        if dst == src or dst == src + 1:
            self._on_page_click_cb(src)
            return

        if self._on_reorder:
            self._on_reorder(src, dst)

    def _on_hover_motion(self, event):
        cy  = self._canvas.canvasy(event.y)
        idx = self._y_to_page_idx(cy)

        if idx == self._hover_idx: return
        self._hide_del_badge()
        self._hover_idx = idx
        if idx is None or self._drag_started: return

        doc = self._get_doc()
        if not doc or doc.page_count <= 1: return

        coords = self._canvas.coords(f"thumb_border_{idx}")
        if coords:
            x0, y0, x1, y1 = coords
            bx = x1 - 1
            by = y0 + 1
        else:
            tw, th = self._thumb_size()
            x_off  = (THUMB_PANEL_W - tw) // 2
            y_top  = self._slot_y(idx)
            bx = x_off + tw - 1
            by = y_top + 1

        badge_bg = self._canvas.create_rectangle(
            bx - 16, by, bx, by + 16,
            fill="#C03030", outline="", tags="del_badge",
        )
        badge_lbl = self._canvas.create_text(
            bx - 8, by + 8,
            text="✕", fill="#FFFFFF",
            font=("Helvetica", 8, "bold"), tags="del_badge",
        )
        self._del_btn_id = badge_bg

        for item in (badge_bg, badge_lbl):
            self._canvas.tag_bind(item, "<ButtonPress-1>", lambda e, i=idx: self._on_del_badge_click(i))
            self._canvas.tag_bind(item, "<Enter>", lambda e: None)
        self._canvas.tag_raise("del_badge")

    def _on_canvas_leave(self, event):
        self._hide_del_badge()
        self._hover_idx = None

    def _hide_del_badge(self):
        self._canvas.delete("del_badge")
        self._del_btn_id = None

    def _on_del_badge_click(self, idx: int):
        self._hide_del_badge()
        self._hover_idx = None
        if self._on_delete_page:
            self._on_delete_page(idx)

    def _on_right_click(self, event):
        cy  = self._canvas.canvasy(event.y)
        idx = self._y_to_page_idx(cy)
        doc = self._get_doc()
        if not doc: return

        menu = tk.Menu(self._canvas, tearoff=0,
                       bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
                       activebackground=PALETTE["accent_dim"],
                       activeforeground=PALETTE["accent_light"],
                       font=("Helvetica", 9), relief="flat", bd=1)

        if idx is not None:
            menu.add_command(label=f"  Page {idx + 1} of {doc.page_count}", state="disabled", font=("Helvetica", 8, "bold"))
            menu.add_separator()
            menu.add_command(label="  Add blank page before", command=lambda: self._on_add_page and self._on_add_page(idx - 1))
            menu.add_command(label="  Add blank page after", command=lambda: self._on_add_page and self._on_add_page(idx))
            menu.add_command(label="  Duplicate page", command=lambda: self._on_duplicate_page and self._on_duplicate_page(idx))
            menu.add_separator()
            menu.add_command(label="  ↺  Rotate Left  (−90°)", command=lambda: self._on_rotate_page and self._on_rotate_page(idx, -90))
            menu.add_command(label="  ↻  Rotate Right (+90°)", command=lambda: self._on_rotate_page and self._on_rotate_page(idx, 90))
            menu.add_separator()
            can_delete = doc.page_count > 1
            menu.add_command(label="  ✕  Delete page", command=lambda: self._on_delete_page and self._on_delete_page(idx), state="normal" if can_delete else "disabled")
        else:
            menu.add_command(label="  Add blank page at end", command=self._on_add_at_end)

        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_add_at_end(self):
        doc = self._get_doc()
        if doc and self._on_add_page:
            self._on_add_page(doc.page_count - 1)

    def _on_scroll(self, event):
        if event.num == 4:
            self._canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self._canvas.yview_scroll(1, "units")
        elif hasattr(event, "delta"):
            self._canvas.yview_scroll(-1 * (event.delta // 120), "units")
        self._on_view_changed()