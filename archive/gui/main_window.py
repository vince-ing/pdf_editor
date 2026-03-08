# src/gui/main_window.py
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

from src.services.page_service        import PageService
from src.services.image_service       import ImageService
from src.services.text_service        import TextService
from src.services.annotation_service  import AnnotationService
from src.services.redaction_service   import RedactionService
from src.services.image_conversion    import ImageConversionService
from src.services.toc_service         import TocService           
from src.commands.snapshot            import DocumentSnapshot
from src.commands.toc_commands        import ModifyTocCommand 

from src.gui.theme import PALETTE, RENDER_DPI
from src.gui.history_manager  import HistoryManager
from src.gui.app_context      import AppContext
from src.gui.viewport_manager import ViewportManager
from src.gui.tools.tool_manager import ToolManager
from src.gui.ui_manager import UIManager

from src.gui.controllers.tts_controller       import TtsController
from src.gui.controllers.ocr_controller       import OcrController
from src.gui.controllers.document_controller  import DocumentController
from src.gui.controllers.history_controller   import HistoryController
from src.gui.controllers.window_controller    import WindowController
from src.gui.controllers.thumbnail_controller import ThumbnailController

from src.utils.settings_manager import SettingsManager
from src.utils.task_manager     import BackgroundTaskManager
from src.utils.font_loader      import load_custom_fonts

try:
    from src.services.merge_split_service  import MergeSplitService
    _HAS_MERGE_SPLIT = True
except ImportError:
    _HAS_MERGE_SPLIT = False

class InteractivePDFEditor:
    """The Root Dependency Injector. Initializes core services, views, and controllers."""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Editor")
        self.root.minsize(900, 640)
        self.root.configure(bg=PALETTE["bg_dark"])
        self.root.overrideredirect(True)
        
        self.task_manager = BackgroundTaskManager(self.root)
        DocumentSnapshot.sweep_orphaned_files()

        # ── 1. Settings & Services ────────────────────────────────────────────
        self.settings = SettingsManager()
        self.root.geometry(self.settings.get("window_geometry", "1280x860+0+0"))
        
        self.page_service             = PageService()
        self.text_service             = TextService()
        self.image_service            = ImageService()
        self.annotation_service       = AnnotationService()
        self.redaction_service        = RedactionService()
        self.image_conversion_service = ImageConversionService()
        self.toc_service              = TocService()
        if _HAS_MERGE_SPLIT: self.merge_split_service = MergeSplitService()

        self._history = HistoryManager()

        # ── 2. View / UI Layer ────────────────────────────────────────────────
        self.ui = UIManager(root, self, has_merge_split=_HAS_MERGE_SPLIT)
        self.canvas = self.ui.canvas_area.canvas

        # ── 3. Core State Managers ────────────────────────────────────────────
        self.viewport = ViewportManager(
            root=self.root, canvas=self.canvas, get_doc=lambda: self.doc,
            callbacks={
                "on_page_changed": self._on_page_changed, "on_zoom_changed": self._update_zoom_label,
                "on_render_complete": lambda: self.tool_manager.rescale_boxes() if hasattr(self, 'tool_manager') else None,
                "get_layers": self._get_layers_for_page,
            }
        )

        self._ctx = AppContext(self)
        self.tool_manager = ToolManager(
            ctx=self._ctx, settings=self.settings,
            services={"text": self.text_service, "image": self.image_service, "annotation": self.annotation_service, "redaction": self.redaction_service},
            ui_callbacks={
                "root": self.root, "set_cursor": lambda c: self.canvas.config(cursor=c),
                "set_status_tool": self.ui.status_bar.set_tool, "set_icon_active": self.ui.icon_toolbar.set_active_tool,
                "render_props": self.ui.right_panel.render_tool_props, "select_props_tab": self.ui.right_panel.select_properties_tab,
                "show_redact_confirm": self.ui.right_panel.show_redact_confirm, "hide_redact_confirm": self.ui.right_panel.hide_redact_confirm,
                "update_hit_display": self.ui.canvas_area.update_hit_display, "clear_hit_display": self.ui.canvas_area.clear_hit_display,
                "mark_dirty": self._mark_dirty, "mark_thumb_dirty": self.ui.right_panel.thumb.mark_dirty, "navigate_to": self._navigate_to
            }
        )
        self._ctx.on_tool_state_change = self.tool_manager.on_tool_state_change

        # ── 4. Feature Controllers ────────────────────────────────────────────
        self.document_controller = DocumentController(
            root=self.root, image_conversion_service=self.image_conversion_service,
            merge_split_service=getattr(self, "merge_split_service", None),
            history=self._history, settings=self.settings, viewport=self.viewport, tool_manager=self.tool_manager,
            ui={
                "rebuild_recent_menu": self.ui.rebuild_recent_menu, "hide_startup_screen": self.ui.hide_startup_screen,
                "show_startup_screen": self.ui.show_startup_screen, "thumb_reset": self.ui.right_panel.thumb.reset,
                "refresh_toc": lambda: self.ui.right_panel.refresh_toc(self.toc_service.get_toc(self.doc) if self.doc else []), 
                "flash_status": self.ui.flash_status, "set_top_bar_title": self.ui.set_top_bar_title,
                "thumb_reset_for_images": self.ui.right_panel.thumb.reset_for_images, "update_page_label": self.ui.right_panel.update_page_label,
                "set_page_size": self.ui.status_bar.set_page_size, "thumb_refresh_all_borders": self.ui.right_panel.thumb.refresh_all_borders,
                "thumb_scroll_to_active": self.ui.right_panel.thumb.scroll_to_active,
            }
        )

        self.history_controller = HistoryController(
            history_manager=self._history, viewport=self.viewport, right_panel=self.ui.right_panel,
            get_doc=lambda: self.doc, flash_status=self.ui.flash_status, mark_dirty=self._mark_dirty
        )

        self.tts_controller = TtsController(
            root=self.root, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            canvas_area=self.ui.canvas_area, viewport=self.viewport, flash_status=self.ui.flash_status,
            get_selection_text=lambda: (self.tool_manager.get_tool("select_text")._selection_text() if self.tool_manager.get_tool("select_text") else "")
        )

        self.ocr_controller = OcrController(
            root=self.root, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            task_manager=self.task_manager, status_bar=self.ui.status_bar, viewport=self.viewport,
            push_history=self.history_controller.push, mark_dirty=self._mark_dirty, flash_status=self.ui.flash_status
        )

        self.thumbnail_controller = ThumbnailController(
            get_doc=lambda: self.doc, viewport=self.viewport, document_controller=self.document_controller,
            history_controller=self.history_controller, get_right_panel=lambda: self.ui.right_panel,
            page_service=self.page_service, mark_dirty=self._mark_dirty, flash_status=self.ui.flash_status,
            navigate_to=self._navigate_to
        )

        self.window_controller = WindowController(
            root=self.root, settings=self.settings,
            callbacks={
                "open": self.document_controller.open_pdf, "save": self.document_controller.save_pdf, "save_as": self.document_controller.save_pdf_as,
                "undo": self.history_controller.undo, "redo": self.history_controller.redo,
                "zoom_in": self.viewport.zoom_in, "zoom_out": self.viewport.zoom_out, "zoom_reset": self.viewport.zoom_reset,
                "zoom_fit_width": self.viewport.zoom_fit_width, "zoom_fit_page": self.viewport.zoom_fit_page,
                "prev_page": self._prev_page, "next_page": self._next_page, "on_escape": self._on_escape,
                "copy": self.tool_manager.copy_selected_text, "toggle_search": self.ui.toggle_search_bar,
                "search_next": lambda: self.tool_manager.get_tool("redact").navigate_next() if self.tool_manager.get_tool("redact") else None,
                "search_prev": lambda: self.tool_manager.get_tool("redact").navigate_prev() if self.tool_manager.get_tool("redact") else None,
                "toggle_inspector": self.ui.toggle_inspector, "select_tool": self.tool_manager.select_tool,
                "flash_status": self.ui.flash_status, "on_closing": self._on_closing
            }
        )

        # ── 5. Final State Sync ───────────────────────────────────────────────
        self.tool_manager.select_tool("text")
        self.ui.update_view_mode_buttons(self.viewport.continuous_mode)
        self.ui.update_zoom_label(self.viewport.scale_factor, RENDER_DPI)
        self.ui.top_bar.set_inspector_active(True)

        self.root.after(50,  self.ui.rebuild_recent_menu)
        self.root.after(60,  self.ui.show_startup_screen)

    # ── Orchestrator Properties & Routing Helpers ─────────────────────────────
    
    @property
    def doc(self): return self.document_controller.doc if hasattr(self, 'document_controller') else None

    @property
    def current_page_idx(self) -> int: return self.viewport.current_page_idx if hasattr(self, 'viewport') else 0

    def _mark_dirty(self) -> None:
        if hasattr(self, 'document_controller'): self.document_controller.mark_dirty()

    def _push_history(self, cmd) -> None:
        if hasattr(self, 'history_controller'): self.history_controller.push(cmd)

    def _prev_page(self) -> None:
        if self.doc and self.current_page_idx > 0: self._navigate_to(self.current_page_idx - 1)

    def _next_page(self) -> None:
        if self.doc and self.current_page_idx < self.doc.page_count - 1: self._navigate_to(self.current_page_idx + 1)

    def _on_page_jump(self, page_num: int) -> None:
        if not self.doc: return
        if 0 <= page_num - 1 < self.doc.page_count: self._navigate_to(page_num - 1)
        else: self.ui.flash_status(f"Page {page_num} out of range (1–{self.doc.page_count})", color=PALETTE["warning"])

    def _navigate_to(self, idx: int) -> None:
        self.tool_manager.commit_all_boxes()
        if self.tool_manager.current_tool: self.tool_manager.current_tool.deactivate()
        self.viewport.navigate_to(idx)
        if self.tool_manager.current_tool: self.tool_manager.current_tool.activate()

    def _toc_navigate(self, page_idx: int) -> None:
        if self.doc and 0 <= page_idx < self.doc.page_count: self._navigate_to(page_idx)

    def _toc_changed(self, new_toc: list) -> None:
        if not self.doc: return
        cmd = ModifyTocCommand(self.doc, self.toc_service, new_toc)
        try:
            cmd.execute()
            self._push_history(cmd)
            self._mark_dirty()
            self.viewport.render()
            self.ui.flash_status("Bookmarks updated", duration_ms=2000)
        except Exception as ex:
            messagebox.showerror("Bookmark Error", str(ex))
            self.ui.right_panel.refresh_toc(self.toc_service.get_toc(self.doc) if self.doc else [])

    def _on_page_changed(self, idx: int) -> None:
        if not self.doc: return
        page = self.doc.get_page(idx)
        self.ui.on_page_changed(idx, self.doc.page_count, page.width, page.height)

    def _update_zoom_label(self, scale: float) -> None:
        self.ui.update_zoom_label(scale, RENDER_DPI)

    def _get_layers_for_page(self, page_idx: int) -> list[dict]:
        layers = []
        sel = self.tool_manager.get_tool("select_text")
        if sel and sel.get_highlight_rects_for_page(page_idx):
            layers.append({"rects": sel.get_highlight_rects_for_page(page_idx), "color": (74, 144, 217), "alpha": 0.35})
        rt = self.tool_manager.get_tool("redact")
        if rt and getattr(rt, "has_search_hits", False):
            active, inactive = rt.get_highlight_rects_for_page(page_idx)
            if inactive: layers.append({"rects": inactive, "color": (123, 63, 191), "alpha": 0.45})
            if active: layers.append({"rects": active, "color": (255, 184, 0), "alpha": 0.65})
        return layers

    def _on_escape(self) -> None:
        if self.ui.canvas_area.search_bar_visible: self.ui.toggle_search_bar()
        elif self.document_controller.is_staging_mode: self.document_controller.exit_staging_mode()
        else: self.tool_manager.dismiss_boxes()

    def _on_closing(self) -> None:
        if self.document_controller.unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "Save before closing?")
            if ans is None: return
            if ans and not self.document_controller.save_pdf(): return
            
        if hasattr(self, "viewport"):
            for after_id in [self.viewport._cont_after_id, self.viewport._scroll_after_id]:
                if after_id:
                    try: self.root.after_cancel(after_id)
                    except Exception: pass
                    
        thumb = getattr(self.ui.right_panel, "thumb", None)
        if thumb:
            for attr in ("_after_id", "_render_after_id"):
                aid = getattr(thumb, attr, None)
                if aid:
                    try: self.root.after_cancel(aid)
                    except Exception: pass
                    
        self.history_controller.clear()
        
        # Save Settings Before Exit
        if hasattr(self, "window_controller"): self.window_controller.save_state()
        if hasattr(self, "settings"): self.settings.save()
        
        try: self.tts_controller.shutdown()
        except Exception: pass
        if self.doc:
            try: self.doc.close()
            except Exception: pass
        self.root.quit()

if __name__ == "__main__":
    load_custom_fonts()
    root = tk.Tk()
    InteractivePDFEditor(root)
    root.mainloop()
    try: root.destroy()
    except Exception: pass