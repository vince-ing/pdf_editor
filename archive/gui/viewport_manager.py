# src/gui/viewport_manager.py
from __future__ import annotations

import tkinter as tk
from typing import Callable, Any

from src.gui.theme import PALETTE, RENDER_DPI, MIN_SCALE, MAX_SCALE, SCALE_STEP, PAD_XL
from src.utils.selection_compositor import composite_selection

class ViewportManager:
    """
    Handles all PDF rendering, zoom math, continuous scroll offsets, 
    and canvas image caching. Decoupled from application state and tools.
    """
    def __init__(
        self,
        root: tk.Tk,
        canvas: tk.Canvas,
        get_doc: Callable[[], Any],
        callbacks: dict[str, Callable],
    ) -> None:
        self.root = root
        self.canvas = canvas
        self.get_doc = get_doc
        self.callbacks = callbacks  # Expected: on_page_changed, on_zoom_changed, on_render_complete, get_layers
        
        # View State
        self.scale_factor: float = RENDER_DPI
        self.continuous_mode: bool = True
        self.current_page_idx: int = 0
        
        # Coordinate Offsets
        self.page_offset_x: float = PAD_XL
        self.page_offset_y: float = PAD_XL
        
        # Rendering Cache
        self.tk_image = None
        self._cont_images: dict = {}
        
        # Debounce and State Flags
        self._zoom_after_id = None
        self._scroll_after_id = None
        self._cont_after_id = None
        self._pinch_snapshot = None
        self._zoom_restoring = False
        self._cont_mode_switch = False
        self._target_scale = RENDER_DPI
        self._cont_cw = 0
        self._CONT_GAP = 20

    def set_view_mode(self, continuous: bool) -> None:
        if self.continuous_mode == continuous:
            return
        self.continuous_mode = continuous
        self._cont_images.clear()
        if continuous:
            self._zoom_restoring = True
            self._cont_mode_switch = True
            self.render()
            self._zoom_restoring = False
            self.schedule_cont_render(self.current_page_idx)
        else:
            self.render()

    def navigate_to(self, idx: int) -> None:
        self.current_page_idx = idx
        if self.continuous_mode:
            self._update_cont_offsets(idx)
            self._render_cont_page_refresh(idx)
            self._scroll_to_current_cont()
            self._notify_page_changed(idx)
            self.root.after(100, lambda: self.schedule_cont_render(idx))
        else:
            self.render()

    def invalidate_cache(self, page_idx: int | None = None) -> None:
        if page_idx is None:
            self._cont_images.clear()
        else:
            for k in [k for k in list(self._cont_images.keys()) if k[0] == page_idx]:
                self.canvas.delete(f"page_img_{k[0]}")
                del self._cont_images[k]

    # ── Rendering Pipeline ────────────────────────────────────────────────────

    def render(self) -> None:
        if not self.get_doc():
            return
        if self.continuous_mode:
            self._render_continuous()
        else:
            self._render_single()
        self._notify_render_complete()

    def _render_single(self) -> None:
        doc = self.get_doc()
        page = doc.get_page(self.current_page_idx)
        ppm = page.render_to_ppm(scale=self.scale_factor)
        self.tk_image = self._make_page_image(ppm, self.current_page_idx)
        iw = int(page.width * self.scale_factor)
        ih = int(page.height * self.scale_factor)
        cw = self.canvas.winfo_width()
        
        self.page_offset_x = max(PAD_XL, (cw - iw) // 2)
        self.page_offset_y = PAD_XL
        ox, oy = self.page_offset_x, self.page_offset_y
        
        self.canvas.delete("page_img", "page_shadow", "page_bg", "textsel")
        self.canvas.create_rectangle(
            ox+4, oy+4, ox+iw+4, oy+ih+4,
            fill=PALETTE["page_shadow"], outline="",
            stipple="gray25", tags="page_shadow")
        self.canvas.create_image(
            ox, oy, anchor=tk.NW, image=self.tk_image, tags="page_img")
        self.canvas.config(scrollregion=(0, 0, ox+iw+50, oy+ih+50))
        self._notify_page_changed(self.current_page_idx)

    def _render_continuous(self) -> None:
        if self._cont_after_id:
            self.root.after_cancel(self._cont_after_id)
            self._cont_after_id = None
            
        doc = self.get_doc()
        n = doc.page_count
        self._cont_cw = self.canvas.winfo_width()
        cw = self._cont_cw
        total_h = self._CONT_GAP
        max_iw = 0
        heights, widths = [], []
        
        for i in range(n):
            p = doc.get_page(i)
            iw = int(p.width * self.scale_factor)
            ih = int(p.height * self.scale_factor)
            heights.append(ih)
            widths.append(iw)
            max_iw = max(max_iw, iw)
            total_h += ih + self._CONT_GAP
            
        self.canvas.delete("page_img", "page_shadow", "page_bg", "textsel")
        self.canvas.config(scrollregion=(0, 0, max(cw, max_iw + 80), total_h))

        if self._cont_mode_switch:
            self._cont_mode_switch = False
            y_top = self._cont_page_top(self.current_page_idx)
            if total_h > 0:
                self.canvas.yview_moveto(max(0.0, y_top / total_h))

        y = self._CONT_GAP
        for i in range(n):
            iw, ih = widths[i], heights[i]
            ox = max(PAD_XL, (cw - iw) // 2)
            self.canvas.create_rectangle(
                ox, y, ox+iw, y+ih, fill=PALETTE.get("page_bg", "#FFFFFF"), outline="", tags=("page_bg", f"page_bg_{i}"))
            self.canvas.create_rectangle(
                ox+4, y+4, ox+iw+4, y+ih+4, fill=PALETTE["page_shadow"], outline="", stipple="gray25", tags=("page_shadow", f"page_shadow_{i}"))
            self.canvas.tag_lower(f"page_shadow_{i}", f"page_bg_{i}")
            y += ih + self._CONT_GAP
            
        self._update_cont_offsets(self.current_page_idx)
        self._notify_page_changed(self.current_page_idx)

        IMMEDIATE = 1
        immediate_range = range(max(0, self.current_page_idx - IMMEDIATE), min(n, self.current_page_idx + IMMEDIATE + 1))
        for i in immediate_range:
            p = doc.get_page(i)
            iw = int(p.width * self.scale_factor)
            ih = int(p.height * self.scale_factor)
            self._render_cont_page(i, iw, ih, cw)

        self._prune_cont_cache(self.current_page_idx)
        self.schedule_cont_render(self.current_page_idx)

    def _render_cont_page(self, idx: int, iw: int, ih: int, cw: int) -> None:
        doc = self.get_doc()
        if not doc or idx >= doc.page_count:
            return
        key = (idx, self.scale_factor)
        if key not in self._cont_images:
            try:
                page = doc.get_page(idx)
                ppm = page.render_to_ppm(scale=self.scale_factor)
                self._cont_images[key] = self._make_page_image(ppm, idx)
            except Exception:
                return
        img = self._cont_images[key]
        y = self._cont_page_top(idx)
        ox = max(PAD_XL, (cw - iw) // 2)
        self.canvas.delete(f"page_img_{idx}")
        self.canvas.create_image(ox, y, anchor=tk.NW, image=img, tags=("page_img", f"page_img_{idx}"))
        self.canvas.tag_lower(f"page_bg_{idx}", f"page_img_{idx}")

    def _render_cont_page_refresh(self, page_idx: int) -> None:
        if not self.get_doc() or not self.continuous_mode:
            return
        p = self.get_doc().get_page(page_idx)
        iw = int(p.width * self.scale_factor)
        ih = int(p.height * self.scale_factor)
        cw = getattr(self, "_cont_cw", self.canvas.winfo_width())
        self._render_cont_page(page_idx, iw, ih, cw)

    def _make_page_image(self, ppm: bytes, page_idx: int) -> tk.PhotoImage:
        layers = self.callbacks.get("get_layers", lambda i: [])(page_idx)
        return composite_selection(ppm_bytes=ppm, scale=self.scale_factor, layers=layers)

    def schedule_cont_render(self, active_idx: int) -> None:
        if self._cont_after_id:
            self.root.after_cancel(self._cont_after_id)
            self._cont_after_id = None
        if not self.get_doc() or not self.continuous_mode:
            return

        n = self.get_doc().page_count
        cw = getattr(self, "_cont_cw", self.canvas.winfo_width())
        start_idx, end_idx = self._get_visible_cont_pages()
        BUFFER = 2
        start_idx = max(0, start_idx - BUFFER)
        end_idx = min(n - 1, end_idx + BUFFER)

        order = []
        if start_idx <= active_idx <= end_idx:
            order.append(active_idx)
        for i in range(start_idx, end_idx + 1):
            if i != active_idx: order.append(i)

        def _render_one(remaining):
            if not remaining or not self.get_doc() or not self.continuous_mode:
                self._cont_after_id = None
                return
            idx = remaining[0]
            rest = remaining[1:]
            p = self.get_doc().get_page(idx)
            iw = int(p.width * self.scale_factor)
            ih = int(p.height * self.scale_factor)
            self._render_cont_page(idx, iw, ih, cw)
            self._cont_after_id = self.root.after(5, lambda: _render_one(rest))

        _render_one(order)

    # ── Scroll & Math Helpers ─────────────────────────────────────────────────

    def _cont_page_top(self, idx: int) -> int:
        doc = self.get_doc()
        if not doc: return 0
        y = self._CONT_GAP
        for i in range(idx):
            p = doc.get_page(i)
            y += int(p.height * self.scale_factor) + self._CONT_GAP
        return y

    def _cont_page_at_y(self, canvas_y: float) -> int:
        doc = self.get_doc()
        if not doc: return 0
        y = self._CONT_GAP
        for i in range(doc.page_count):
            p = doc.get_page(i)
            ih = int(p.height * self.scale_factor)
            if canvas_y <= y + ih: return i
            y += ih + self._CONT_GAP
        return doc.page_count - 1

    def _update_cont_offsets(self, idx: int) -> None:
        doc = self.get_doc()
        if not doc: return
        p = doc.get_page(idx)
        iw = int(p.width * self.scale_factor)
        cw = self.canvas.winfo_width()
        self.page_offset_x = max(PAD_XL, (cw - iw) // 2)
        self.page_offset_y = self._cont_page_top(idx)

    def _get_visible_cont_pages(self) -> tuple[int, int]:
        if not self.get_doc(): return 0, 0
        top = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        return self._cont_page_at_y(top), self._cont_page_at_y(bottom)

    def _prune_cont_cache(self, active_idx: int) -> None:
        if not self.continuous_mode or not self.get_doc(): return
        start_idx, end_idx = self._get_visible_cont_pages()
        BUFFER = 4
        keep_indices = set(range(start_idx - BUFFER, end_idx + BUFFER + 1))
        keys_to_delete = [k for k in list(self._cont_images.keys()) if k[0] not in keep_indices]
        for k in keys_to_delete:
            self.canvas.delete(f"page_img_{k[0]}")
            del self._cont_images[k]

    def _scroll_to_current_cont(self) -> None:
        if not self.get_doc(): return
        self.canvas.update_idletasks()
        y_top = self._cont_page_top(self.current_page_idx)
        bbox = self.canvas.bbox("all")
        if bbox and bbox[3] > 0:
            self.canvas.yview_moveto(max(0.0, y_top / bbox[3]))

    # ── Zoom Logic ────────────────────────────────────────────────────────────

    def zoom_in(self) -> None:
        self._set_zoom(min(MAX_SCALE, self._target_scale + SCALE_STEP), debounce=True)

    def zoom_out(self) -> None:
        self._set_zoom(max(MIN_SCALE, self._target_scale - SCALE_STEP), debounce=True)

    def zoom_reset(self) -> None:
        self._set_zoom(RENDER_DPI, debounce=False)

    def zoom_fit_width(self) -> None:
        if not self.get_doc(): return
        page = self.get_doc().get_page(self.current_page_idx)
        cw = self.canvas.winfo_width()
        if cw < 10:
            self.root.after(60, self.zoom_fit_width)
            return
        new_scale = round(max(MIN_SCALE, min(MAX_SCALE, (cw - 2 * PAD_XL) / page.width)), 3)
        self._set_zoom(new_scale, debounce=False)

    def zoom_fit_page(self) -> None:
        if not self.get_doc(): return
        page = self.get_doc().get_page(self.current_page_idx)
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.root.after(60, self.zoom_fit_page)
            return
        scale_w = (cw - 2 * PAD_XL) / page.width
        scale_h = (ch - 2 * PAD_XL) / page.height
        new_scale = round(max(MIN_SCALE, min(MAX_SCALE, min(scale_w, scale_h))), 3)
        self._set_zoom(new_scale, debounce=False)

    def _set_zoom(self, s: float, debounce: bool = False, preserve_scroll: bool = False) -> None:
        self._target_scale = round(s, 3)
        self.callbacks.get("on_zoom_changed", lambda s: None)(self._target_scale)
        self._zoom_preserve_scroll = preserve_scroll
        if self._zoom_after_id:
            self.root.after_cancel(self._zoom_after_id)
        if debounce:
            self._zoom_after_id = self.root.after(150, self._apply_zoom)
        else:
            self._apply_zoom()

    def _apply_zoom(self) -> None:
        self._zoom_after_id = None
        new_scale = self._target_scale

        if self.continuous_mode and self.get_doc() and not getattr(self, "_zoom_preserve_scroll", False):
            snap = getattr(self, "_pinch_snapshot", None)
            if snap:
                page_idx, frac, old_page = snap["page_idx"], snap["frac"], snap["page"]
                self._pinch_snapshot = None
            else:
                canvas_top = self.canvas.canvasy(0)
                page_idx = self.current_page_idx
                page_top = self._cont_page_top(page_idx)
                old_page = self.get_doc().get_page(page_idx)
                old_page_h = int(old_page.height * self.scale_factor)
                frac = max(0.0, (canvas_top - page_top) / old_page_h if old_page_h > 0 else 0.0)

            self.scale_factor = new_scale
            self.invalidate_cache()
            self.render()

            def _restore():
                self._zoom_restoring = True
                try:
                    new_page_top = self._cont_page_top(page_idx)
                    new_page_h = int(old_page.height * self.scale_factor)
                    target_y = new_page_top + frac * new_page_h
                    bbox = self.canvas.bbox("all")
                    if bbox and bbox[3] > 0:
                        self.canvas.yview_moveto(max(0.0, target_y / bbox[3]))
                finally:
                    self._zoom_restoring = False
                self.schedule_cont_render(self.current_page_idx)

            self.canvas.after(0, _restore)
        else:
            self._pinch_snapshot = None
            self.scale_factor = new_scale
            self.invalidate_cache()
            self.render()

        self._zoom_preserve_scroll = False

    # ── Input Events ──────────────────────────────────────────────────────────

    def on_canvas_scrolled(self) -> None:
        if not self.continuous_mode: return
        if self._zoom_restoring: return
        self._pinch_snapshot = None
        if self._scroll_after_id:
            self.root.after_cancel(self._scroll_after_id)
        
        top = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        idx = self._cont_page_at_y((top + bottom) / 2)
        
        if idx != self.current_page_idx:
            self.current_page_idx = idx
            self._update_cont_offsets(idx)
            self._notify_page_changed(idx)
            
        self._scroll_after_id = self.root.after(50, lambda: (
            self._prune_cont_cache(idx),
            self.schedule_cont_render(idx)
        ))

    def on_ctrl_scroll(self, event: tk.Event) -> None:
        direction = 1 if (event.num == 4 or getattr(event, "delta", 0) > 0) else -1
        step = SCALE_STEP * 2.5
        new_target = max(MIN_SCALE, min(MAX_SCALE, self._target_scale + direction * step))

        if not getattr(self, "_pinch_snapshot", None) and self.continuous_mode and self.get_doc():
            canvas_top = self.canvas.canvasy(0)
            page_idx = self.current_page_idx
            page_top = self._cont_page_top(page_idx)
            old_page = self.get_doc().get_page(page_idx)
            old_page_h = int(old_page.height * self.scale_factor)
            frac = max(0.0, (canvas_top - page_top) / old_page_h if old_page_h > 0 else 0.0)
            self._pinch_snapshot = {"page_idx": page_idx, "frac": frac, "page": old_page}

        self._set_zoom(new_target, debounce=True)

    # ── Notification Wrappers ─────────────────────────────────────────────────

    def _notify_page_changed(self, idx: int) -> None:
        if "on_page_changed" in self.callbacks:
            self.callbacks["on_page_changed"](idx)

    def _notify_render_complete(self) -> None:
        if "on_render_complete" in self.callbacks:
            self.callbacks["on_render_complete"]()