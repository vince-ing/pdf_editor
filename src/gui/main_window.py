# src/gui/main_window.py
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from src.services.page_service        import PageService
from src.services.image_service       import ImageService
from src.services.text_service        import TextService
from src.services.annotation_service  import AnnotationService
from src.services.redaction_service   import RedactionService
from src.services.image_conversion    import ImageConversionService
from src.services.toc_service         import TocService           
from src.commands.snapshot            import DocumentSnapshot
from src.commands.toc_commands        import ModifyTocCommand 

from src.gui.theme import PALETTE, RENDER_DPI, PAD_M
from src.gui.history_manager  import HistoryManager
from src.gui.app_context      import AppContext
from src.gui.viewport_manager import ViewportManager
from src.gui.tools.tool_manager import ToolManager

# Phase 3 & 4 Controllers
from src.gui.controllers.tts_controller       import TtsController
from src.gui.controllers.ocr_controller       import OcrController
from src.gui.controllers.document_controller  import DocumentController
from src.gui.controllers.history_controller   import HistoryController
from src.gui.controllers.window_controller    import WindowController
from src.gui.controllers.thumbnail_controller import ThumbnailController

# UI Components
from src.gui.components.top_bar      import TopBar
from src.gui.components.icon_toolbar import IconToolbar
from src.gui.components.right_panel  import RightPanel
from src.gui.components.canvas_area  import CanvasArea
from src.gui.components.status_bar   import StatusBar

from src.utils.recent_files   import RecentFiles
from src.utils.task_manager   import BackgroundTaskManager
from src.utils.font_loader    import load_custom_fonts

try:
    from src.services.merge_split_service  import MergeSplitService
    _HAS_MERGE_SPLIT = True
except ImportError:
    _HAS_MERGE_SPLIT = False


class InteractivePDFEditor:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Editor")
        self.root.geometry("1280x860")
        self.root.minsize(900, 640)
        self.root.configure(bg=PALETTE["bg_dark"])
        self.root.overrideredirect(True)
        
        self.task_manager = BackgroundTaskManager(self.root)
        DocumentSnapshot.sweep_orphaned_files()

        # ── 1. Services ───────────────────────────────────────────────────────
        self.page_service             = PageService()
        self.text_service             = TextService()
        self.image_service            = ImageService()
        self.annotation_service       = AnnotationService()
        self.redaction_service        = RedactionService()
        self.image_conversion_service = ImageConversionService()
        self.toc_service              = TocService()
        if _HAS_MERGE_SPLIT: self.merge_split_service = MergeSplitService()

        self._history = HistoryManager()
        self._recent  = RecentFiles()

        # ── 2. UI Foundation ──────────────────────────────────────────────────
        self._apply_ttk_style()
        self._build_ui()

        # ── 3. Core Managers ──────────────────────────────────────────────────
        self.viewport = ViewportManager(
            root=self.root, canvas=self._canvas_area.canvas, get_doc=lambda: self.doc,
            callbacks={
                "on_page_changed": self._on_page_changed, "on_zoom_changed": self._update_zoom_label,
                "on_render_complete": lambda: self.tool_manager.rescale_boxes() if hasattr(self, 'tool_manager') else None,
                "get_layers": self._get_layers_for_page,
            }
        )

        self._ctx = AppContext(self)
        self.tool_manager = ToolManager(
            ctx=self._ctx,
            services={"text": self.text_service, "image": self.image_service, "annotation": self.annotation_service, "redaction": self.redaction_service},
            ui_callbacks={
                "root": self.root, "set_cursor": lambda c: self.canvas.config(cursor=c),
                "set_status_tool": self._status_bar.set_tool, "set_icon_active": self._icon_toolbar.set_active_tool,
                "render_props": self._right_panel.render_tool_props, "select_props_tab": self._right_panel.select_properties_tab,
                "show_redact_confirm": self._right_panel.show_redact_confirm, "hide_redact_confirm": self._right_panel.hide_redact_confirm,
                "update_hit_display": self._canvas_area.update_hit_display, "clear_hit_display": self._canvas_area.clear_hit_display,
                "mark_dirty": self._mark_dirty, "mark_thumb_dirty": self._right_panel.thumb.mark_dirty, "navigate_to": self._navigate_to
            }
        )
        self._ctx.on_tool_state_change = self.tool_manager.on_tool_state_change
        
        # ── 4. Controllers ────────────────────────────────────────────────────
        self.document_controller = DocumentController(
            root=self.root, image_conversion_service=self.image_conversion_service,
            merge_split_service=getattr(self, "merge_split_service", None),
            history=self._history, recent_files=self._recent, viewport=self.viewport, tool_manager=self.tool_manager,
            ui={
                "rebuild_recent_menu": self._rebuild_recent_menu, "hide_startup_screen": self._hide_startup_screen,
                "show_startup_screen": self._show_startup_screen, "thumb_reset": self._right_panel.thumb.reset,
                "refresh_toc": lambda: self._right_panel.refresh_toc(self.toc_service.get_toc(self.doc) if self.doc else []), 
                "flash_status": self._flash_status, "set_top_bar_title": self._top_bar.set_title,
                "thumb_reset_for_images": self._right_panel.thumb.reset_for_images, "update_page_label": self._right_panel.update_page_label,
                "set_page_size": self._status_bar.set_page_size, "thumb_refresh_all_borders": self._right_panel.thumb.refresh_all_borders,
                "thumb_scroll_to_active": self._right_panel.thumb.scroll_to_active,
            }
        )

        self.history_controller = HistoryController(
            history_manager=self._history, viewport=self.viewport, right_panel=self._right_panel,
            get_doc=lambda: self.doc, flash_status=self._flash_status, mark_dirty=self._mark_dirty
        )

        self.tts_controller = TtsController(
            root=self.root, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            canvas_area=self._canvas_area, viewport=self.viewport, flash_status=self._flash_status,
            get_selection_text=lambda: (self.tool_manager.get_tool("select_text")._selection_text() if self.tool_manager.get_tool("select_text") else "")
        )

        self.ocr_controller = OcrController(
            root=self.root, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            task_manager=self.task_manager, status_bar=self._status_bar, viewport=self.viewport,
            push_history=self.history_controller.push, mark_dirty=self._mark_dirty, flash_status=self._flash_status
        )

        self.thumbnail_controller = ThumbnailController(
            get_doc=lambda: self.doc, viewport=self.viewport, document_controller=self.document_controller,
            history_controller=self.history_controller, get_right_panel=lambda: self._right_panel,
            page_service=self.page_service, mark_dirty=self._mark_dirty, flash_status=self._flash_status,
            navigate_to=self._navigate_to
        )

        self.window_controller = WindowController(
            root=self.root,
            callbacks={
                "open": self.document_controller.open_pdf, "save": self.document_controller.save_pdf, "save_as": self.document_controller.save_pdf_as,
                "undo": self.history_controller.undo, "redo": self.history_controller.redo,
                "zoom_in": self.viewport.zoom_in, "zoom_out": self.viewport.zoom_out, "zoom_reset": self.viewport.zoom_reset,
                "zoom_fit_width": self.viewport.zoom_fit_width, "zoom_fit_page": self.viewport.zoom_fit_page,
                "prev_page": self._prev_page, "next_page": self._next_page, "on_escape": self._on_escape,
                "copy": self.tool_manager.copy_selected_text, "toggle_search": self._toggle_search_bar,
                "search_next": lambda: self.tool_manager.get_tool("redact").navigate_next() if self.tool_manager.get_tool("redact") else None,
                "search_prev": lambda: self.tool_manager.get_tool("redact").navigate_prev() if self.tool_manager.get_tool("redact") else None,
                "toggle_inspector": self._toggle_inspector, "select_tool": self.tool_manager.select_tool,
                "flash_status": self._flash_status, "on_closing": self._on_closing
            }
        )

        # ── 5. Sync Initial State ─────────────────────────────────────────────
        self._right_panel.tool_style_state = self.tool_manager.style
        self.tool_manager.select_tool("text")

        self._startup_frame = None
        self._update_view_mode_buttons()
        self._update_zoom_label(self.viewport.scale_factor)
        self._top_bar.set_inspector_active(True)

        self.root.after(50,  self._rebuild_recent_menu)
        self.root.after(60,  self._show_startup_screen)


    # ── Orchestrator Properties & Proxies ─────────────────────────────────────
    
    @property
    def doc(self): return self.document_controller.doc if hasattr(self, 'document_controller') else None

    @property
    def current_page_idx(self) -> int: return self.viewport.current_page_idx if hasattr(self, 'viewport') else 0

    @property
    def scale_factor(self) -> float: return self.viewport.scale_factor if hasattr(self, 'viewport') else RENDER_DPI

    def _mark_dirty(self) -> None:
        if hasattr(self, 'document_controller'): self.document_controller.mark_dirty()

    def _push_history(self, cmd) -> None:
        if hasattr(self, 'history_controller'): self.history_controller.push(cmd)

    def _flash_status(self, message: str, color=None, duration_ms=3000) -> None:
        self._status_bar.flash(message, color=color, duration_ms=duration_ms)


    # ── UI Construction ───────────────────────────────────────────────────────

    def _apply_ttk_style(self) -> None:
        s = ttk.Style()
        try: s.theme_use("clam")
        except Exception: pass
        s.configure("TCombobox", fieldbackground=PALETTE["bg_hover"], background=PALETTE["bg_hover"], foreground=PALETTE["fg_primary"], selectbackground=PALETTE["accent_dim"], selectforeground=PALETTE["fg_primary"], bordercolor=PALETTE["border"], lightcolor=PALETTE["border"], darkcolor=PALETTE["border"], arrowcolor=PALETTE["fg_secondary"], insertcolor=PALETTE["fg_primary"])
        s.map("TCombobox", fieldbackground=[("readonly", PALETTE["bg_hover"])], selectbackground=[("readonly", PALETTE["accent_dim"])])
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar", background=PALETTE["bg_panel"], troughcolor=PALETTE["bg_dark"], bordercolor=PALETTE["bg_panel"], arrowcolor=PALETTE["fg_dim"], gripcount=0, relief="flat")
            s.map(f"{orient}.TScrollbar", background=[("active", PALETTE["bg_hover"])])
        s.configure("Right.TNotebook", background=PALETTE["bg_panel"], borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("Right.TNotebook.Tab", background=PALETTE["bg_panel"], foreground=PALETTE["fg_dim"], padding=[PAD_M, 6], font=("Helvetica Neue", 9), borderwidth=0)
        s.map("Right.TNotebook.Tab", background=[("selected", PALETTE["bg_card"])], foreground=[("selected", PALETTE["fg_primary"])])

    def _build_ui(self) -> None:
        self._status_bar = StatusBar(self.root)
        self._top_bar = TopBar(
            self.root,
            callbacks={
                "open": lambda: self.document_controller.open_pdf(), "save": lambda: self.document_controller.save_pdf(), "save_as": lambda: self.document_controller.save_pdf_as(),
                "ocr_page": lambda: self.ocr_controller.ocr_current_page(), "ocr_all_pages": lambda: self.ocr_controller.ocr_all_pages(),
                "tts_page": lambda: self.tts_controller.read_page(), "tts_all": lambda: self.tts_controller.read_all(), "tts_selection": lambda: self.tts_controller.read_selection(),
                "start_image_staging": lambda: self.document_controller.start_image_staging(), "open_merge_split": lambda: self.document_controller.open_merge_split_dialog(),
                "rotate_left": lambda: self._rotate(-90), "rotate_right": lambda: self._rotate(90),
                "add_page": self._add_page, "delete_page": self._delete_page, "undo": lambda: self.history_controller.undo(), "redo": lambda: self.history_controller.redo(),
                "zoom_in": lambda: self.viewport.zoom_in(), "zoom_out": lambda: self.viewport.zoom_out(), "zoom_reset": lambda: self.viewport.zoom_reset(),
                "zoom_fit_width": lambda: self.viewport.zoom_fit_width(), "zoom_fit_page": lambda: self.viewport.zoom_fit_page(),
                "set_single_mode": self._set_single_mode, "set_continuous_mode": self._set_continuous_mode,
                "toggle_search_bar": self._toggle_search_bar, "toggle_inspector": self._toggle_inspector,
                "wc_close": lambda: self.window_controller.close(), "wc_minimize": lambda: self.window_controller.minimize(), "wc_maximize": lambda: self.window_controller.maximize(),
            },
            has_merge_split=_HAS_MERGE_SPLIT,
        )

        self._body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        self._body.pack(fill=tk.BOTH, expand=True)

        self._icon_toolbar = IconToolbar(
            self._body, on_tool_select=lambda t: self.tool_manager.select_tool(t),
            page_action_callbacks={"rotate_left": lambda: self._rotate(-90), "rotate_right": lambda: self._rotate(90), "add_page": self._add_page, "delete_page": self._delete_page, "ocr_page": lambda: self.ocr_controller.ocr_current_page()},
        )

        self._right_panel = RightPanel(
            self._body, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            thumbnail_callbacks={
                "root": self.root, 
                "page_click": lambda idx: self.thumbnail_controller.page_click(idx), 
                "reorder": lambda s, d: self.thumbnail_controller.reorder(s, d),
                "add_page": lambda idx: self.thumbnail_controller.add_page(idx), 
                "delete_page": lambda idx: self.thumbnail_controller.delete_page(idx), 
                "duplicate_page": lambda idx: self.thumbnail_controller.duplicate_page(idx),
                "rotate_page": lambda idx, angle: self.thumbnail_controller.rotate_page(idx, angle), 
                "prev_page": self._prev_page, "next_page": self._next_page, "on_page_jump": self._on_page_jump,
            },
            tool_style_state={}, on_tool_style_change=lambda k, v: self.tool_manager.on_tool_style_change(k, v),
            toc_callbacks={"on_navigate": self._toc_navigate, "on_toc_changed": self._toc_changed, "get_page_count": lambda: self.doc.page_count if self.doc else 0},
        )

        self._canvas_area = CanvasArea(
            self._body,
            canvas_callbacks={
                "on_click": lambda e: self.tool_manager.handle_click(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)),
                "on_drag": lambda e: self.tool_manager.handle_drag(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)),
                "on_release": lambda e: self.tool_manager.handle_release(self.canvas.canvasx(e.x), self.canvas.canvasy(e.y)),
                "on_mousewheel": self._on_mousewheel, "on_ctrl_scroll": lambda e: self.viewport.on_ctrl_scroll(e) if hasattr(self, 'viewport') else None,
                "on_motion": self._on_mouse_motion, "on_configure": self._on_canvas_configure, "on_scroll_changed": lambda: self.viewport.on_canvas_scrolled() if hasattr(self, 'viewport') else None,
            },
            search_bar_callbacks={
                "on_find": self._search_bar_find, "on_next": lambda: self.tool_manager.get_tool("redact").navigate_next() if self.tool_manager.get_tool("redact") else None,
                "on_prev": lambda: self.tool_manager.get_tool("redact").navigate_prev() if self.tool_manager.get_tool("redact") else None,
                "on_redact_one": self._search_bar_redact_one, "on_redact_all": self._search_bar_redact_all, "on_close": self._toggle_search_bar,
            },
        )
        self.canvas = self._canvas_area.canvas

    def _toggle_inspector(self) -> None:
        self._right_panel.toggle_visibility()
        self._top_bar.set_inspector_active(getattr(self._right_panel, "_visible", True))

    def _show_startup_screen(self) -> None:
        if self.doc: return
        self._hide_startup_screen()
        frame = tk.Frame(self.canvas, bg=PALETTE["bg_dark"])
        self._startup_frame = frame
        inner = tk.Frame(frame, bg=PALETTE["bg_dark"])
        inner.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(inner, text="◼", bg=PALETTE["bg_dark"], fg=PALETTE["accent"], font=("Helvetica Neue", 52)).pack(pady=(0, 4))
        tk.Label(inner, text="PDF Editor", bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"], font=("Helvetica Neue", 22, "bold")).pack()
        tk.Label(inner, text="Open a PDF file to get started", bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"], font=("Helvetica Neue", 10)).pack(pady=(4, 20))
        
        tk.Button(inner, text="  Open PDF…  ", command=lambda: self.document_controller.open_pdf(), bg=PALETTE["accent"], fg=PALETTE["fg_inverse"], activebackground=PALETTE["accent_light"], activeforeground=PALETTE["fg_inverse"], font=("Helvetica Neue", 12, "bold"), relief="flat", bd=0, padx=28, pady=10, cursor="hand2", highlightthickness=0).pack(pady=(0, 28))

        recents = self._recent.get()
        if recents:
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(0, 12))
            tk.Label(inner, text="RECENT FILES", bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"], font=("Helvetica Neue", 8, "bold")).pack(anchor="w", pady=(0, 6))
            for p in recents:
                row = tk.Frame(inner, bg=PALETTE["bg_dark"], cursor="hand2")
                row.pack(fill=tk.X, pady=1)
                name, directory = os.path.basename(p), os.path.dirname(p)
                if len(directory) > 48: directory = "…" + directory[-46:]
                nl = tk.Label(row, text=name, bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"], font=("Helvetica Neue", 10), anchor="w", cursor="hand2")
                nl.pack(anchor="w")
                pl = tk.Label(row, text=directory, bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"], font=("Helvetica Neue", 8), anchor="w", cursor="hand2")
                pl.pack(anchor="w")

                def _enter(e, r=row, n=nl, pp=pl): r.config(bg=PALETTE["bg_hover"]); n.config(bg=PALETTE["bg_hover"], fg=PALETTE["accent_light"]); pp.config(bg=PALETTE["bg_hover"])
                def _leave(e, r=row, n=nl, pp=pl): r.config(bg=PALETTE["bg_dark"]); n.config(bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"]); pp.config(bg=PALETTE["bg_dark"])
                def _click(e, fp=p): self.document_controller.open_pdf_path(fp)

                for w in (row, nl, pl): w.bind("<Enter>", _enter); w.bind("<Leave>", _leave); w.bind("<Button-1>", _click)
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(4, 0))
        frame.place(x=0, y=0, relwidth=1, relheight=1)

    def _hide_startup_screen(self) -> None:
        if self._startup_frame:
            try: self._startup_frame.destroy()
            except Exception: pass
            self._startup_frame = None

    def _rebuild_recent_menu(self) -> None:
        menu_kw = dict(tearoff=0, bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"], activebackground=PALETTE["accent_dim"], activeforeground=PALETTE["accent_light"], font=("Helvetica Neue", 9), relief="flat", bd=1)
        menu = tk.Menu(self.root, **menu_kw)
        recents = self._recent.get()
        if recents:
            for p in recents:
                label, dirname = os.path.basename(p), os.path.dirname(p)
                if len(dirname) > 40: dirname = "…" + dirname[-38:]
                menu.add_command(label=f"  {label}\n  {dirname}", command=lambda fp=p: self.document_controller.open_recent(fp))
            menu.add_separator()
            menu.add_command(label="  Clear recent files", command=self._clear_recent, foreground=PALETTE["fg_dim"])
        else: menu.add_command(label="  No recent files", state="disabled")
        self._top_bar.set_recent_menu(menu)

    def _clear_recent(self) -> None:
        self._recent.clear()
        self._rebuild_recent_menu()
        if self._startup_frame: self._show_startup_screen()

    # ── Orchestrator Document Navigation ──────────────────────────────────────

    def _prev_page(self) -> None:
        if self.doc and self.current_page_idx > 0: self._navigate_to(self.current_page_idx - 1)

    def _next_page(self) -> None:
        if self.doc and self.current_page_idx < self.doc.page_count - 1: self._navigate_to(self.current_page_idx + 1)

    def _on_page_jump(self, page_num: int) -> None:
        if not self.doc: return
        if 0 <= page_num - 1 < self.doc.page_count: self._navigate_to(page_num - 1)
        else: self._flash_status(f"Page {page_num} out of range (1–{self.doc.page_count})", color=PALETTE["warning"])

    def _navigate_to(self, idx: int) -> None:
        self.tool_manager.commit_all_boxes()
        if self.tool_manager.current_tool: self.tool_manager.current_tool.deactivate()
        self.viewport.navigate_to(idx)
        if self.tool_manager.current_tool: self.tool_manager.current_tool.activate()

    def _rotate(self, angle: int) -> None:
        if self.doc: self.thumbnail_controller.rotate_page(self.current_page_idx, angle)

    def _add_page(self) -> None:
        if self.doc: self.thumbnail_controller.add_page(self.current_page_idx)

    def _delete_page(self) -> None:
        if self.doc: self.thumbnail_controller.delete_page(self.current_page_idx)

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
            self._flash_status("Bookmarks updated", duration_ms=2000)
        except Exception as ex:
            messagebox.showerror("Bookmark Error", str(ex))
            self._right_panel.refresh_toc(self.toc_service.get_toc(self.doc) if self.doc else [])

    # ── View Callbacks & Updates ──────────────────────────────────────────────

    def _on_page_changed(self, idx: int) -> None:
        if not self.doc: return
        page = self.doc.get_page(idx)
        self._right_panel.update_page_label(idx + 1, self.doc.page_count)
        self._status_bar.set_page_size(f"{int(page.width)} × {int(page.height)} pt")
        self._right_panel.thumb.refresh_all_borders()
        self._right_panel.thumb.scroll_to_active()

    def _update_zoom_label(self, scale: float) -> None:
        pct = int(scale / RENDER_DPI * 100)
        self._top_bar.set_zoom_label(f"{pct}%")
        self._status_bar.set_zoom(f"Zoom {pct}%")

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

    def _set_single_mode(self) -> None:
        self.tool_manager.commit_all_boxes()
        self.viewport.set_view_mode(continuous=False)
        self._update_view_mode_buttons()

    def _set_continuous_mode(self) -> None:
        self.tool_manager.commit_all_boxes()
        self.viewport.set_view_mode(continuous=True)
        self._update_view_mode_buttons()

    def _update_view_mode_buttons(self) -> None:
        self._top_bar.update_view_mode_buttons(self.viewport.continuous_mode)

    # ── Search Bar UI ─────────────────────────────────────────────────────────

    def _toggle_search_bar(self) -> None:
        if self._canvas_area.search_bar_visible:
            self._canvas_area.hide_search_bar()
            self._search_bar_clear()
        else:
            self._canvas_area.show_search_bar()
            if self.tool_manager.active_tool_name != "redact": self.tool_manager.select_tool("redact")

    def _search_bar_find(self) -> None:
        if not self.doc or not self._canvas_area.search_query: return
        if self.tool_manager.active_tool_name != "redact": self.tool_manager.select_tool("redact")
        rt = self.tool_manager.get_tool("redact")
        if rt and rt.search_all_pages(self._canvas_area.search_query, case_sensitive=self._canvas_area.search_case_sensitive) == 0:
            self._canvas_area.update_hit_display(-1, 0)
            self._flash_status(f'No matches for "{self._canvas_area.search_query}"', color=PALETTE["fg_secondary"])

    def _search_bar_redact_one(self) -> None:
        if rt := self.tool_manager.get_tool("redact"): rt.redact_current_hit()
        self._right_panel.hide_redact_confirm()

    def _search_bar_redact_all(self) -> None:
        if rt := self.tool_manager.get_tool("redact"): rt.redact_all_hits()
        self._right_panel.hide_redact_confirm()

    def _search_bar_clear(self) -> None:
        if rt := self.tool_manager.get_tool("redact"):
            if rt.has_search_hits: rt.cancel_search()
        self._canvas_area.clear_hit_display()

    # ── Canvas Navigation Inputs ──────────────────────────────────────────────

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if hasattr(self, "_config_after_id") and self._config_after_id: self.root.after_cancel(self._config_after_id)
        self._config_after_id = self.root.after(150, lambda: (self.viewport.render(), setattr(self, '_config_after_id', None)))

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        if self.viewport.continuous_mode:
            idx = self.viewport._cont_page_at_y(cy)
            if idx != self.current_page_idx: self._navigate_to(idx)
        return ((cx - self.viewport.page_offset_x) / self.scale_factor, (cy - self.viewport.page_offset_y) / self.scale_factor)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4: self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: self.canvas.yview_scroll(1, "units")
        else: self.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_mouse_motion(self, event: tk.Event) -> None:
        if not self.doc: return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self._status_bar.set_coords(*self._canvas_to_pdf(cx, cy))
        self.tool_manager.handle_motion(cx, cy)

    # ── Shutdown Logic ────────────────────────────────────────────────────────

    def _on_escape(self) -> None:
        if self._canvas_area.search_bar_visible: self._toggle_search_bar()
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
        
        thumb = getattr(self._right_panel, "thumb", None)
        if thumb:
            for attr in ("_after_id", "_render_after_id"):
                aid = getattr(thumb, attr, None)
                if aid:
                    try: self.root.after_cancel(aid)
                    except Exception: pass
        
        self.history_controller.clear()
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