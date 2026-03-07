# src/gui/main_window.py
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image, ImageTk
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

from src.core.document import PDFDocument
from src.services.page_service        import PageService
from src.services.image_service       import ImageService
from src.services.text_service        import TextService
from src.services.annotation_service  import AnnotationService
from src.services.redaction_service   import RedactionService
from src.services.image_conversion    import ImageConversionService

from src.commands.snapshot       import DocumentSnapshot
from src.commands.rotate_page    import RotatePageCommand
from src.commands.page_ops       import ReorderPagesCommand, DuplicatePageCommand
from src.commands.convert_images import ConvertImagesToPdfCommand
from src.commands.toc_commands   import ModifyTocCommand 

from src.gui.theme import PALETTE, RENDER_DPI, PAD_M
from src.gui.history_manager  import HistoryManager
from src.gui.app_context      import AppContext
from src.gui.viewport_manager import ViewportManager
from src.gui.tools.tool_manager import ToolManager

# Phase 3 Controllers
from src.gui.controllers.tts_controller import TtsController
from src.gui.controllers.ocr_controller import OcrController

# UI Components
from src.gui.components.top_bar      import TopBar
from src.gui.components.icon_toolbar import IconToolbar, TOOL_KEY_MAP
from src.gui.components.right_panel  import RightPanel
from src.gui.components.canvas_area  import CanvasArea
from src.gui.components.status_bar   import StatusBar

from src.utils.recent_files   import RecentFiles
from src.utils.task_manager   import BackgroundTaskManager
from src.utils.font_loader    import load_custom_fonts
from src.services.toc_service import TocService           

try:
    from src.services.merge_split_service  import MergeSplitService
    from src.gui.panels.merge_split_dialog import MergeSplitDialog
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

        # ── Services ──────────────────────────────────────────────────────────
        self.page_service             = PageService()
        self.text_service             = TextService()
        self.image_service            = ImageService()
        self.annotation_service       = AnnotationService()
        self.redaction_service        = RedactionService()
        self.image_conversion_service = ImageConversionService()
        self.toc_service              = TocService()
        if _HAS_MERGE_SPLIT:
            self.merge_split_service = MergeSplitService()

        # ── Document / view state ──────────────────────────────────────────────
        self.doc: PDFDocument | None = None
        self._current_path: str | None = None
        self._unsaved_changes = False

        self._is_staging_mode = False
        self._staging_images: list[str] = []
        self._staging_ocr_var = tk.BooleanVar(value=False)

        self._history = HistoryManager(on_change=self._on_history_change)
        self._recent  = RecentFiles()

        self._apply_ttk_style()
        self._build_ui()

        # ── Managers (Phase 1 & 2) ────────────────────────────────────────────
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
        
        # ── Controllers (Phase 3) ─────────────────────────────────────────────
        self.tts_controller = TtsController(
            root=self.root, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            canvas_area=self._canvas_area, viewport=self.viewport, flash_status=self._flash_status,
            get_selection_text=lambda: (self.tool_manager.get_tool("select_text")._selection_text() if self.tool_manager.get_tool("select_text") else "")
        )

        self.ocr_controller = OcrController(
            root=self.root, get_doc=lambda: self.doc, get_current_page=lambda: self.current_page_idx,
            task_manager=self.task_manager, status_bar=self._status_bar, viewport=self.viewport,
            push_history=self._push_history, mark_dirty=self._mark_dirty, flash_status=self._flash_status
        )

        # Sync Initial State
        self._right_panel.tool_style_state = self.tool_manager.style
        self.tool_manager.select_tool("text")

        self._startup_frame = None
        self._update_view_mode_buttons()
        self._update_zoom_label(self.viewport.scale_factor)
        self._top_bar.set_inspector_active(True)

        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.after(50,  self._rebuild_recent_menu)
        self.root.after(60,  self._show_startup_screen)

    @property
    def current_page_idx(self) -> int: return self.viewport.current_page_idx if hasattr(self, 'viewport') else 0

    @property
    def scale_factor(self) -> float: return self.viewport.scale_factor if hasattr(self, 'viewport') else RENDER_DPI

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
                "open": self._open_pdf, "save": self._save_pdf, "save_as": self._save_pdf_as,
                "ocr_page": lambda: self.ocr_controller.ocr_current_page(), "ocr_all_pages": lambda: self.ocr_controller.ocr_all_pages(),
                "tts_page": lambda: self.tts_controller.read_page(), "tts_all": lambda: self.tts_controller.read_all(), "tts_selection": lambda: self.tts_controller.read_selection(),
                "start_image_staging": self._start_image_staging, "open_merge_split": self._open_merge_split_dialog,
                "rotate_left": lambda: self._rotate(-90), "rotate_right": lambda: self._rotate(90),
                "add_page": self._add_page, "delete_page": self._delete_page, "undo": self._undo, "redo": self._redo,
                "zoom_in": lambda: self.viewport.zoom_in(), "zoom_out": lambda: self.viewport.zoom_out(), "zoom_reset": lambda: self.viewport.zoom_reset(),
                "zoom_fit_width": lambda: self.viewport.zoom_fit_width(), "zoom_fit_page": lambda: self.viewport.zoom_fit_page(),
                "set_single_mode": self._set_single_mode, "set_continuous_mode": self._set_continuous_mode,
                "toggle_search_bar": self._toggle_search_bar, "toggle_inspector": self._toggle_inspector,
                "wc_close": self._wc_close, "wc_minimize": self._wc_minimize, "wc_maximize": self._wc_maximize,
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
                "root": self.root, "page_click": self._thumb_page_click, "reorder": self._thumb_reorder,
                "add_page": self._thumb_add_page, "delete_page": self._thumb_delete_page, "duplicate_page": self._thumb_duplicate_page,
                "rotate_page": self._thumb_rotate_page, "prev_page": self._prev_page, "next_page": self._next_page, "on_page_jump": self._on_page_jump,
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

    def _bind_keys(self) -> None:
        r = self.root
        r.bind("<Control-o>", lambda e: self._open_pdf())
        r.bind("<Control-s>", lambda e: self._save_pdf())
        r.bind("<Control-S>", lambda e: self._save_pdf_as())
        r.bind("<Control-z>", lambda e: self._undo())
        r.bind("<Control-y>", lambda e: self._redo())
        r.bind("<Control-equal>", lambda e: self.viewport.zoom_in())
        r.bind("<Control-minus>", lambda e: self.viewport.zoom_out())
        r.bind("<Control-0>", lambda e: self.viewport.zoom_reset())
        r.bind("<Control-1>", lambda e: self.viewport.zoom_fit_width())
        r.bind("<Control-2>", lambda e: self.viewport.zoom_fit_page())
        r.bind("<Left>", lambda e: self._prev_page())
        r.bind("<Right>", lambda e: self._next_page())
        r.bind("<Escape>", lambda e: self._on_escape())
        r.bind("<Control-c>", lambda e: self.tool_manager.copy_selected_text())
        r.bind("<Control-f>", lambda e: self._toggle_search_bar())
        r.bind("<F3>", lambda e: self.tool_manager.get_tool("redact").navigate_next() if self.tool_manager.get_tool("redact") else None)
        r.bind("<Shift-F3>", lambda e: self.tool_manager.get_tool("redact").navigate_prev() if self.tool_manager.get_tool("redact") else None)
        r.bind("<Control-t>", lambda e: self._toggle_inspector())
        r.bind("<KeyPress>", self._on_key_press)

    def _on_key_press(self, event: tk.Event) -> None:
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Text)): return
        key = event.keysym.lower()
        if key in TOOL_KEY_MAP:
            tool = TOOL_KEY_MAP[key]
            self.tool_manager.select_tool(tool)
            self._flash_status(f"Tool: {tool.replace('_', ' ').title()}  [{key.upper()}]", color=PALETTE["accent_light"], duration_ms=1200)

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
        
        tk.Button(inner, text="  Open PDF…  ", command=self._open_pdf, bg=PALETTE["accent"], fg=PALETTE["fg_inverse"], activebackground=PALETTE["accent_light"], activeforeground=PALETTE["fg_inverse"], font=("Helvetica Neue", 12, "bold"), relief="flat", bd=0, padx=28, pady=10, cursor="hand2", highlightthickness=0).pack(pady=(0, 28))

        recents = self._recent.get()
        if recents:
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(0, 12))
            tk.Label(inner, text="RECENT FILES", bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"], font=("Helvetica Neue", 8, "bold")).pack(anchor="w", pady=(0, 6))
            
            for p in recents:
                row = tk.Frame(inner, bg=PALETTE["bg_dark"], cursor="hand2")
                row.pack(fill=tk.X, pady=1)
                
                name = os.path.basename(p)
                directory = os.path.dirname(p)
                if len(directory) > 48:
                    directory = "…" + directory[-46:]
                
                nl = tk.Label(row, text=name, bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"], font=("Helvetica Neue", 10), anchor="w", cursor="hand2")
                nl.pack(anchor="w")
                pl = tk.Label(row, text=directory, bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"], font=("Helvetica Neue", 8), anchor="w", cursor="hand2")
                pl.pack(anchor="w")

                def _enter(e, r=row, n=nl, pp=pl):
                    r.config(bg=PALETTE["bg_hover"])
                    n.config(bg=PALETTE["bg_hover"], fg=PALETTE["accent_light"])
                    pp.config(bg=PALETTE["bg_hover"])
                    
                def _leave(e, r=row, n=nl, pp=pl):
                    r.config(bg=PALETTE["bg_dark"])
                    n.config(bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"])
                    pp.config(bg=PALETTE["bg_dark"])
                    
                def _click(e, fp=p):
                    self._open_pdf_path(fp)

                for w in (row, nl, pl):
                    w.bind("<Enter>", _enter)
                    w.bind("<Leave>", _leave)
                    w.bind("<Button-1>", _click)
                    
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(4, 0))
            
        frame.place(x=0, y=0, relwidth=1, relheight=1)

    def _hide_startup_screen(self) -> None:
        if self._startup_frame:
            try: self._startup_frame.destroy()
            except Exception: pass
            self._startup_frame = None

    def _rebuild_recent_menu(self) -> None:
        menu_kw = dict(
            tearoff=0, bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            activebackground=PALETTE["accent_dim"], activeforeground=PALETTE["accent_light"],
            font=("Helvetica Neue", 9), relief="flat", bd=1
        )
        menu = tk.Menu(self.root, **menu_kw)
        recents = self._recent.get()
        
        if recents:
            for p in recents:
                label = os.path.basename(p)
                dirname = os.path.dirname(p)
                if len(dirname) > 40:
                    dirname = "…" + dirname[-38:]
                menu.add_command(
                    label=f"  {label}\n  {dirname}",
                    command=lambda fp=p: self._open_recent(fp)
                )
            menu.add_separator()
            menu.add_command(label="  Clear recent files", command=self._clear_recent, foreground=PALETTE["fg_dim"])
        else:
            menu.add_command(label="  No recent files", state="disabled")
            
        self._top_bar.set_recent_menu(menu)

    def _clear_recent(self) -> None:
        self._recent.clear()
        self._rebuild_recent_menu()
        if self._startup_frame:
            self._show_startup_screen()

    def _open_pdf(self) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes.\nSave before opening?")
            if ans is None: return
            if ans and not self._save_pdf(): return
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")])
        if path: self._open_pdf_path(path)

    def _open_pdf_path(self, path: str) -> None:
        self._is_staging_mode = False
        self.tool_manager.commit_all_boxes()
        if self.doc: self.doc.close()
        try: self.doc = PDFDocument(path)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open:\n{ex}")
            return
        self.viewport.current_page_idx = 0
        self._current_path = path
        self._unsaved_changes = False
        self._history.clear()
        self.viewport.invalidate_cache()
        self._recent.add(path)
        self._rebuild_recent_menu()
        self._hide_startup_screen()
        self._update_title()
        self.viewport.render()
        self._right_panel.thumb.reset()
        self._refresh_toc() 
        self.root.after(80, self.viewport.zoom_fit_width)

    def _open_recent(self, path: str) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes.\nSave before opening?")
            if ans is None: return
            if ans and not self._save_pdf(): return
        self._open_pdf_path(path)

    def _save_pdf(self) -> bool:
        if self._is_staging_mode: return self._generate_pdf_from_staging()
        if not self.doc: return False
        if not self._current_path: return self._save_pdf_as()
        self.tool_manager.commit_all_boxes()
        try:
            self.doc.save(self._current_path, incremental=True)
            self._unsaved_changes = False
            self._history.mark_saved()
            self._update_title()
            self._flash_status("✓ Saved")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    def _save_pdf_as(self) -> bool:
        if not self.doc: return False
        self.tool_manager.commit_all_boxes()
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], initialfile=os.path.basename(self._current_path) if self._current_path else "document.pdf")
        if not path: return False
        try:
            self.doc.save(path)
            self._current_path = path
            self._unsaved_changes = False
            self.doc.path = path
            self._history.mark_saved()
            self._update_title()
            self._flash_status(f"✓ Saved as {os.path.basename(path)}")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    def _refresh_toc(self) -> None:
        self._right_panel.refresh_toc(self.toc_service.get_toc(self.doc) if self.doc else [])

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
            self._refresh_toc()

    # ── Staging Mode ──────────────────────────────────────────────────────────

    def _get_image_thumbnail(self, path: str, width: int) -> bytes:
        return self.image_conversion_service.get_image_thumbnail(path, width)

    def _start_image_staging(self) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "Save before continuing?")
            if ans is None: return
            if ans and not self._save_pdf(): return
        paths = filedialog.askopenfilenames(title="Select Images to Combine into PDF", filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if not paths: return
        self.tool_manager.commit_all_boxes()
        if self.doc:
            self.doc.close()
            self.doc = None
        self._staging_images = list(paths)
        self._is_staging_mode = True
        self._current_path = None
        self._update_title()
        self._right_panel.thumb.reset_for_images(self._staging_images)
        self._flash_status("Staging: drag thumbnails to reorder, then Save.")
        self._preview_staging_image(0)

    def _preview_staging_image(self, idx: int) -> None:
        if not self._is_staging_mode or idx >= len(self._staging_images): return
        self.viewport.current_page_idx = idx
        path = self._staging_images[idx]
        canvas_w = self.canvas.winfo_width()
        preview_w = int(canvas_w * 0.8 * self.viewport.scale_factor)
        img_bytes = self._get_image_thumbnail(path, width=preview_w)
        if img_bytes:
            self.viewport.tk_image = tk.PhotoImage(data=img_bytes)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_w // 2, 40, anchor=tk.N, image=self.viewport.tk_image, tags="page_img")
            self._right_panel.update_page_label(idx + 1, len(self._staging_images))
            self._status_bar.set_page_size("Image Preview")
            cb = tk.Checkbutton(self.canvas, text="Run OCR (make text selectable)", variable=self._staging_ocr_var, bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"], selectcolor=PALETTE["accent_dim"], activebackground=PALETTE["bg_hover"], highlightthickness=0)
            self.canvas.create_window(canvas_w // 2, 15, window=cb, tags="page_img")
            self._right_panel.thumb.refresh_all_borders()
            self._right_panel.thumb.scroll_to_active()

    def _exit_staging_mode(self) -> None:
        if not self._is_staging_mode: return
        self._is_staging_mode = False
        self._staging_images.clear()
        self.canvas.delete("all")
        self._right_panel.thumb.reset()
        self._show_startup_screen()
        self._flash_status("Cancelled", color=PALETTE["fg_secondary"])

    def _generate_pdf_from_staging(self) -> bool:
        if not self._staging_images: return False
        out_path = filedialog.asksaveasfilename(title="Save Generated PDF", defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], initialfile="Combined_Images.pdf")
        if not out_path: return False
        self.root.config(cursor="watch")
        self.root.update()
        cmd = ConvertImagesToPdfCommand(self.image_conversion_service, self._staging_images, out_path, apply_ocr=self._staging_ocr_var.get())
        try:
            cmd.execute()
            if cmd.success:
                self._flash_status("✓ PDF created")
                self._is_staging_mode = False
                self._staging_images.clear()
                self._staging_ocr_var.set(False)
                self._open_pdf_path(out_path)
                return True
            messagebox.showerror("Error", "Failed to create PDF from images.")
            return False
        finally:
            self.root.config(cursor="")

    # ── Merge / Split ─────────────────────────────────────────────────────────

    def _open_merge_split_dialog(self) -> None:
        if _HAS_MERGE_SPLIT: MergeSplitDialog(root=self.root, service=self.merge_split_service, current_doc=self.doc, on_open_path=self._open_pdf_path)

    # ── Page Management ───────────────────────────────────────────────────────

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

    def _thumb_page_click(self, idx: int) -> None:
        if self._is_staging_mode: self._preview_staging_image(idx)
        elif self.doc and idx != self.current_page_idx: self._navigate_to(idx)

    def _thumb_reorder(self, src_idx: int, dst_idx: int) -> None:
        if self._is_staging_mode:
            if src_idx == dst_idx: return
            path = self._staging_images.pop(src_idx)
            insert_at = max(0, min(dst_idx if dst_idx < src_idx else dst_idx - 1, len(self._staging_images)))
            self._staging_images.insert(insert_at, path)
            self._right_panel.thumb.reset_for_images(self._staging_images)
            self._preview_staging_image(insert_at)
            self._flash_status(f"↕ Moved image {src_idx+1} → {insert_at+1}")
            return
        if not self.doc or src_idx == dst_idx: return
        n = self.doc.page_count
        if not (0 <= src_idx < n) or not (0 <= dst_idx <= n): return
        order = list(range(n))
        order.pop(src_idx)
        insert_at = max(0, min(dst_idx if dst_idx < src_idx else dst_idx - 1, len(order)))
        order.insert(insert_at, src_idx)
        if order == list(range(n)): return
        prev_page = self.current_page_idx
        cmd = ReorderPagesCommand(self.doc, order)
        try: cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            return messagebox.showerror("Reorder Error", str(ex))
        try: self.viewport.current_page_idx = order.index(prev_page)
        except ValueError: self.viewport.current_page_idx = 0
        self._mark_dirty()
        self.viewport.invalidate_cache()
        self._right_panel.thumb.reset()
        self.viewport.render()
        self._push_history(cmd)
        self._flash_status(f"↕ Moved page {src_idx+1} → {insert_at+1}")

    def _thumb_add_page(self, after_idx: int) -> None:
        if not self.doc: return
        try:
            ref = self.doc.get_page(max(0, after_idx))
            self.doc.insert_page(after_idx + 1, width=ref.width, height=ref.height)
        except Exception as ex: return messagebox.showerror("Add Page", str(ex))
        self.viewport.current_page_idx = after_idx + 1
        self._mark_dirty()
        self.viewport.invalidate_cache()
        self._right_panel.thumb.reset()
        self.viewport.render()
        self._flash_status(f"+ Added page at {after_idx+2}")

    def _thumb_delete_page(self, idx: int) -> None:
        if not self.doc: return
        if self.doc.page_count <= 1: return messagebox.showwarning("Cannot Delete", "A PDF must have at least one page.")
        if not messagebox.askyesno("Delete Page", f"Permanently delete page {idx+1}?", icon="warning"): return
        try: self.doc.delete_page(idx)
        except Exception as ex: return messagebox.showerror("Delete", str(ex))
        self.viewport.current_page_idx = min(self.current_page_idx, self.doc.page_count - 1)
        self._mark_dirty()
        self.viewport.invalidate_cache()
        self._right_panel.thumb.reset()
        self.viewport.render()
        self._flash_status(f"✕ Deleted page {idx+1}")

    def _thumb_duplicate_page(self, idx: int) -> None:
        if not self.doc: return
        cmd = DuplicatePageCommand(self.doc, idx)
        try: cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            return messagebox.showerror("Duplicate", str(ex))
        self._push_history(cmd)
        self.viewport.current_page_idx = idx + 1
        self._mark_dirty()
        self.viewport.invalidate_cache()
        self._right_panel.thumb.reset()
        self.viewport.render()
        self._flash_status(f"⧉ Duplicated page {idx+1}")

    def _thumb_rotate_page(self, idx: int, angle: int) -> None:
        if not self.doc: return
        cmd = RotatePageCommand(self.page_service, self.doc, idx, angle)
        try: cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            return messagebox.showerror("Rotate", str(ex))
        self._push_history(cmd)
        self._right_panel.thumb.mark_dirty(idx)
        self.viewport.invalidate_cache(idx)
        if idx == self.current_page_idx: self.viewport.render()
        self._flash_status(f"{'↺' if angle < 0 else '↻'} Rotated page {idx+1}")

    def _rotate(self, angle: int) -> None:
        if self.doc: self._thumb_rotate_page(self.current_page_idx, angle)

    def _add_page(self) -> None:
        if self.doc: self._thumb_add_page(self.current_page_idx)

    def _delete_page(self) -> None:
        if self.doc: self._thumb_delete_page(self.current_page_idx)

    # ── UI Callbacks & Display Updates ────────────────────────────────────────

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

    # ── Canvas Resizing & Scroll Input ────────────────────────────────────────

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

    # ── History Integration ───────────────────────────────────────────────────

    def _push_history(self, cmd) -> None:
        self._history.push(cmd)
        self._right_panel.thumb.mark_dirty(self.current_page_idx)
        self.viewport.invalidate_cache(self.current_page_idx)

    def _on_history_change(self) -> None: self._mark_dirty()

    def _undo(self) -> None:
        if not self._history.can_undo: return self._flash_status("Nothing to undo", color=PALETTE["fg_secondary"])
        try:
            cmd = self._history._history[self._history._idx]
            label = self._history.undo()
            self._after_history_step(cmd)
            self._flash_status(f"↩ Undid {label}")
        except Exception as ex: messagebox.showerror("Undo Error", str(ex))

    def _redo(self) -> None:
        if not self._history.can_redo: return self._flash_status("Nothing to redo", color=PALETTE["fg_secondary"])
        try:
            cmd = self._history._history[self._history._idx + 1]
            label = self._history.redo()
            self._after_history_step(cmd)
            self._flash_status(f"↪ Redid {label}")
        except Exception as ex: messagebox.showerror("Redo Error", str(ex))

    def _after_history_step(self, cmd) -> None:
        if isinstance(cmd, (ReorderPagesCommand, DuplicatePageCommand)) or cmd is None:
            self.viewport.current_page_idx = max(0, min(self.current_page_idx, (self.doc.page_count if self.doc else 0) - 1))
            self.viewport.invalidate_cache()
            self._right_panel.thumb.reset()
        else:
            self._right_panel.thumb.mark_dirty(self.current_page_idx)
            self.viewport.invalidate_cache(self.current_page_idx)
        self.viewport.render()

    def _flash_status(self, message: str, color=None, duration_ms=3000) -> None:
        self._status_bar.flash(message, color=color, duration_ms=duration_ms)

    def _update_title(self) -> None:
        if self._current_path:
            name = os.path.basename(self._current_path)
            marker = " •" if self._unsaved_changes else ""
            title = f"{name}{marker}"
        else:
            title = "PDF Editor" + (" — Untitled •" if self._unsaved_changes else "")
        self.root.title(f"PDF Editor — {title}" if self._current_path else title)
        self._top_bar.set_title(os.path.basename(self._current_path) + (" •" if self._unsaved_changes else "") if self._current_path else "PDF Editor")

    def _mark_dirty(self) -> None:
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    # ── Window Chrome & Process Exit ──────────────────────────────────────────

    def _wc_close(self) -> None: self._on_closing()
    
    def _wc_minimize(self) -> None:
        self.root.withdraw()
        self._min_helper = tk.Toplevel(self.root)
        self._min_helper.title("PDF Editor")
        self._min_helper.geometry("1x1+-10000+-10000")
        self._min_helper.iconify()
        self._min_helper.protocol("WM_DELETE_WINDOW", self._wc_restore)
        self._min_helper.bind("<Map>", lambda e: self._wc_restore())

    def _wc_restore(self) -> None:
        if hasattr(self, "_min_helper") and self._min_helper:
            try: self._min_helper.destroy()
            except Exception: pass
            self._min_helper = None
        self.root.deiconify()

    def _wc_maximize(self) -> None:
        if getattr(self, "_maximized", False):
            geo = getattr(self, "_pre_max_geometry", "1280x860+0+0")
            self.root.geometry(geo)
            self._maximized = False
        else:
            self._pre_max_geometry = self.root.geometry()
            try:
                import ctypes
                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                r = RECT()
                ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
                w, h, x, y = r.right - r.left, r.bottom - r.top, r.left, r.top
            except Exception:
                w, h, x, y = self.root.winfo_screenwidth(), self.root.winfo_screenheight(), 0, 0
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._maximized = True

    def _on_escape(self) -> None:
        if self._canvas_area.search_bar_visible: self._toggle_search_bar()
        elif self._is_staging_mode: self._exit_staging_mode()
        else: self.tool_manager.dismiss_boxes()

    def _on_closing(self) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "Save before closing?")
            if ans is None: return
            if ans and not self._save_pdf(): return
        
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
        
        self._history.clear()
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