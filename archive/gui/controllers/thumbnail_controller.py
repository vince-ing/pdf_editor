# src/gui/controllers/thumbnail_controller.py
from __future__ import annotations
from tkinter import messagebox
from typing import Callable, Any

from src.commands.page_ops import ReorderPagesCommand, DuplicatePageCommand
from src.commands.rotate_page import RotatePageCommand

class ThumbnailController:
    """Manages thumbnail interactions: drag-to-reorder, click-to-navigate, and context menu actions."""
    
    def __init__(
        self,
        get_doc: Callable,
        viewport: Any,
        document_controller: Any,
        history_controller: Any,
        get_right_panel: Callable,
        page_service: Any,
        mark_dirty: Callable,
        flash_status: Callable,
        navigate_to: Callable
    ) -> None:
        self.get_doc = get_doc
        self.viewport = viewport
        self.doc_ctrl = document_controller
        self.history = history_controller
        self.get_right_panel = get_right_panel
        self.page_service = page_service
        self.mark_dirty = mark_dirty
        self.flash_status = flash_status
        self.navigate_to = navigate_to

    def page_click(self, idx: int) -> None:
        if self.doc_ctrl.is_staging_mode:
            self.doc_ctrl.preview_staging_image(idx)
        elif self.get_doc() and idx != self.viewport.current_page_idx:
            self.navigate_to(idx)

    def reorder(self, src_idx: int, dst_idx: int) -> None:
        if self.doc_ctrl.is_staging_mode:
            if src_idx == dst_idx: return
            path = self.doc_ctrl.staging_images.pop(src_idx)
            insert_at = max(0, min(dst_idx if dst_idx < src_idx else dst_idx - 1, len(self.doc_ctrl.staging_images)))
            self.doc_ctrl.staging_images.insert(insert_at, path)
            self.get_right_panel().thumb.reset_for_images(self.doc_ctrl.staging_images)
            self.doc_ctrl.preview_staging_image(insert_at)
            self.flash_status(f"↕ Moved image {src_idx+1} → {insert_at+1}")
            return
            
        doc = self.get_doc()
        if not doc or src_idx == dst_idx: return
        n = doc.page_count
        if not (0 <= src_idx < n) or not (0 <= dst_idx <= n): return
        
        order = list(range(n))
        order.pop(src_idx)
        insert_at = max(0, min(dst_idx if dst_idx < src_idx else dst_idx - 1, len(order)))
        order.insert(insert_at, src_idx)
        
        if order == list(range(n)): return
        prev_page = self.viewport.current_page_idx
        cmd = ReorderPagesCommand(doc, order)
        
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Reorder Error", str(ex))
            return
            
        try: 
            self.viewport.current_page_idx = order.index(prev_page)
        except ValueError: 
            self.viewport.current_page_idx = 0
            
        self.mark_dirty()
        self.viewport.invalidate_cache()
        self.get_right_panel().thumb.reset()
        self.viewport.render()
        self.history.push(cmd)
        self.flash_status(f"↕ Moved page {src_idx+1} → {insert_at+1}")

    def add_page(self, after_idx: int) -> None:
        doc = self.get_doc()
        if not doc: return
        try:
            ref = doc.get_page(max(0, after_idx))
            doc.insert_page(after_idx + 1, width=ref.width, height=ref.height)
        except Exception as ex:
            messagebox.showerror("Add Page", str(ex))
            return
            
        self.viewport.current_page_idx = after_idx + 1
        self.mark_dirty()
        self.viewport.invalidate_cache()
        self.get_right_panel().thumb.reset()
        self.viewport.render()
        self.flash_status(f"+ Added page at {after_idx+2}")

    def delete_page(self, idx: int) -> None:
        doc = self.get_doc()
        if not doc: return
        if doc.page_count <= 1:
            messagebox.showwarning("Cannot Delete", "A PDF must have at least one page.")
            return
        if not messagebox.askyesno("Delete Page", f"Permanently delete page {idx+1}?", icon="warning"): return
        
        try:
            doc.delete_page(idx)
        except Exception as ex:
            messagebox.showerror("Delete", str(ex))
            return
            
        self.viewport.current_page_idx = min(self.viewport.current_page_idx, doc.page_count - 1)
        self.mark_dirty()
        self.viewport.invalidate_cache()
        self.get_right_panel().thumb.reset()
        self.viewport.render()
        self.flash_status(f"✕ Deleted page {idx+1}")

    def duplicate_page(self, idx: int) -> None:
        doc = self.get_doc()
        if not doc: return
        cmd = DuplicatePageCommand(doc, idx)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Duplicate", str(ex))
            return
            
        self.history.push(cmd)
        self.viewport.current_page_idx = idx + 1
        self.mark_dirty()
        self.viewport.invalidate_cache()
        self.get_right_panel().thumb.reset()
        self.viewport.render()
        self.flash_status(f"⧉ Duplicated page {idx+1}")

    def rotate_page(self, idx: int, angle: int) -> None:
        doc = self.get_doc()
        if not doc: return
        cmd = RotatePageCommand(self.page_service, doc, idx, angle)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Rotate", str(ex))
            return
            
        self.history.push(cmd)
        self.get_right_panel().thumb.mark_dirty(idx)
        self.viewport.invalidate_cache(idx)
        if idx == self.viewport.current_page_idx:
            self.viewport.render()
        self.flash_status(f"{'↺' if angle < 0 else '↻'} Rotated page {idx+1}")