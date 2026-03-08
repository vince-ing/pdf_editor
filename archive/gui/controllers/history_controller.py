# src/gui/controllers/history_controller.py
from __future__ import annotations
from tkinter import messagebox

from src.commands.page_ops import ReorderPagesCommand, DuplicatePageCommand
from src.gui.theme import PALETTE

class HistoryController:
    """Manages the history stack, undo/redo execution, and cache invalidation."""
    def __init__(self, history_manager, viewport, right_panel, get_doc, flash_status, mark_dirty):
        self.history = history_manager
        self.viewport = viewport
        self.right_panel = right_panel
        self.get_doc = get_doc
        self.flash_status = flash_status
        self.mark_dirty = mark_dirty

        self.history.on_change = self.mark_dirty

    def push(self, cmd) -> None:
        self.history.push(cmd)
        page_idx = self.viewport.current_page_idx
        self.right_panel.thumb.mark_dirty(page_idx)
        self.viewport.invalidate_cache(page_idx)

    def undo(self) -> None:
        if not self.history.can_undo:
            return self.flash_status("Nothing to undo", color=PALETTE["fg_secondary"])
        try:
            cmd = self.history._history[self.history._idx]
            label = self.history.undo()
            self._after_step(cmd)
            self.flash_status(f"↩ Undid {label}")
        except Exception as ex:
            messagebox.showerror("Undo Error", str(ex))

    def redo(self) -> None:
        if not self.history.can_redo:
            return self.flash_status("Nothing to redo", color=PALETTE["fg_secondary"])
        try:
            cmd = self.history._history[self.history._idx + 1]
            label = self.history.redo()
            self._after_step(cmd)
            self.flash_status(f"↪ Redid {label}")
        except Exception as ex:
            messagebox.showerror("Redo Error", str(ex))

    def _after_step(self, cmd) -> None:
        doc = self.get_doc()
        page_idx = self.viewport.current_page_idx
        if isinstance(cmd, (ReorderPagesCommand, DuplicatePageCommand)) or cmd is None:
            self.viewport.current_page_idx = max(0, min(page_idx, (doc.page_count if doc else 0) - 1))
            self.viewport.invalidate_cache()
            self.right_panel.thumb.reset()
        else:
            self.right_panel.thumb.mark_dirty(page_idx)
            self.viewport.invalidate_cache(page_idx)
        self.viewport.render()
    
    def clear(self) -> None:
        """Clears the history stack."""
        self.history.clear()