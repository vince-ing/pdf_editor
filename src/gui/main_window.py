"""
PDF Editor — Main Window

This class is now a pure orchestrator:
  • Holds all application state (document, history, tools).
  • Instantiates the five UI components and wires their callbacks.
  • Never builds Tkinter widgets directly.
"""

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

from src.commands.insert_text   import InsertTextBoxCommand
from src.commands.rotate_page   import RotatePageCommand
from src.commands.page_ops      import ReorderPagesCommand, DuplicatePageCommand
from src.commands.draw_command  import DrawAnnotationCommand
from src.commands.convert_images import ConvertImagesToPdfCommand
from src.commands.ocr_page      import OcrPageCommand

from src.gui.theme import (
    PALETTE, FONT_MONO, FONT_UI,
    RENDER_DPI, MIN_SCALE, MAX_SCALE, SCALE_STEP,
    PAD_XL, PAD_M,
)
from src.gui.history_manager  import HistoryManager
from src.gui.app_context      import AppContext
from src.gui.widgets.tooltip  import Tooltip
from src.gui.widgets.text_box import TextBox

# UI Components
from src.gui.components.top_bar      import TopBar
from src.gui.components.icon_toolbar import IconToolbar, TOOL_KEY_MAP
from src.gui.components.right_panel  import RightPanel
from src.gui.components.canvas_area  import CanvasArea
from src.gui.components.status_bar   import StatusBar

# Tools
from src.gui.tools.annot_tool  import AnnotationTool
from src.gui.tools.image_tool  import ImageInsertTool, ImageExtractTool
from src.gui.tools.select_tool import SelectTextTool
from src.gui.tools.redact_tool import RedactTool
from src.gui.tools.draw_tool   import DrawTool

from src.utils.recent_files import RecentFiles
from src.utils.selection_compositor import composite_selection

try:
    from src.services.merge_split_service  import MergeSplitService
    from src.gui.panels.merge_split_dialog import MergeSplitDialog
    _HAS_MERGE_SPLIT = True
except ImportError:
    _HAS_MERGE_SPLIT = False


# ══════════════════════════════════════════════════════════════════════════════
#  InteractivePDFEditor — orchestrator
# ══════════════════════════════════════════════════════════════════════════════

class InteractivePDFEditor:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("PDF Editor")
        self.root.geometry("1280x860")
        self.root.minsize(900, 640)
        self.root.configure(bg=PALETTE["bg_dark"])

        # ── Services ──────────────────────────────────────────────────────────
        self.page_service             = PageService()
        self.text_service             = TextService()
        self.image_service            = ImageService()
        self.annotation_service       = AnnotationService()
        self.redaction_service        = RedactionService()
        self.image_conversion_service = ImageConversionService()
        if _HAS_MERGE_SPLIT:
            self.merge_split_service = MergeSplitService()

        # ── Document / view state ──────────────────────────────────────────────
        self.doc: PDFDocument | None = None
        self.current_page_idx  = 0
        self.scale_factor      = RENDER_DPI
        self.tk_image          = None
        self._page_offset_x    = PAD_XL
        self._page_offset_y    = PAD_XL
        self._continuous_mode  = True
        self._cont_images: dict  = {}
        self._cont_after_id      = None
        self._scroll_after_id    = None
        self._current_path: str | None = None
        self._unsaved_changes    = False

        # ── Staging (images → PDF) ────────────────────────────────────────────
        self._is_staging_mode    = False
        self._staging_images: list[str] = []
        self._staging_ocr_var    = tk.BooleanVar(value=False)

        # ── Mutable tool-style state (shared with RightPanel) ─────────────────
        self._style: dict = {
            "annot_stroke_rgb":  (92, 138, 110),
            "annot_fill_rgb":    None,
            "annot_width":       1.5,
            "draw_mode":         "pen",
            "draw_stroke_rgb":   (92, 138, 110),
            "draw_fill_rgb":     None,
            "draw_width":        2.0,
            "draw_opacity":      1.0,
            "font_index":        0,
            "fontsize":          14,
            "text_color":        (0, 0, 0),
            "text_align":        0,
            "redact_fill_color": (0.0, 0.0, 0.0),
            "redact_label":      "",
        }

        # ── Text boxes ────────────────────────────────────────────────────────
        self._text_boxes: list[TextBox] = []
        self._suppress_next_click       = False

        # ── History / recent ──────────────────────────────────────────────────
        self._history = HistoryManager(on_change=self._on_history_change)
        self._recent  = RecentFiles()

        # ── Build UI ──────────────────────────────────────────────────────────
        self._apply_ttk_style()
        self._build_ui()

        # ── AppContext + tools ────────────────────────────────────────────────
        self._ctx = AppContext(self)
        self._ctx.on_tool_state_change = self._on_tool_state_change
        self._tools: dict       = {}
        self._current_tool      = None
        self._active_tool_name  = "text"
        self._init_tools()

        # ── Key bindings ──────────────────────────────────────────────────────
        self._bind_keys()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        self.root.after(50,  self._rebuild_recent_menu)
        self.root.after(60,  self._show_startup_screen)

    # ══════════════════════════════════════════════════════════════════════════
    #  TTK style
    # ══════════════════════════════════════════════════════════════════════════

    def _apply_ttk_style(self) -> None:
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except Exception:
            pass
        s.configure("TCombobox",
                    fieldbackground=PALETTE["bg_hover"],
                    background=PALETTE["bg_hover"],
                    foreground=PALETTE["fg_primary"],
                    selectbackground=PALETTE["accent_dim"],
                    selectforeground=PALETTE["fg_primary"],
                    bordercolor=PALETTE["border"],
                    lightcolor=PALETTE["border"],
                    darkcolor=PALETTE["border"],
                    arrowcolor=PALETTE["fg_secondary"],
                    insertcolor=PALETTE["fg_primary"])
        s.map("TCombobox",
              fieldbackground=[("readonly", PALETTE["bg_hover"])],
              selectbackground=[("readonly", PALETTE["accent_dim"])])
        for orient in ("Vertical", "Horizontal"):
            s.configure(f"{orient}.TScrollbar",
                        background=PALETTE["bg_panel"],
                        troughcolor=PALETTE["bg_dark"],
                        bordercolor=PALETTE["bg_panel"],
                        arrowcolor=PALETTE["fg_dim"],
                        gripcount=0, relief="flat")
            s.map(f"{orient}.TScrollbar",
                  background=[("active", PALETTE["bg_hover"])])
        s.configure("Right.TNotebook",
                    background=PALETTE["bg_panel"], borderwidth=0,
                    tabmargins=[0, 0, 0, 0])
        s.configure("Right.TNotebook.Tab",
                    background=PALETTE["bg_panel"],
                    foreground=PALETTE["fg_dim"],
                    padding=[PAD_M, 6],
                    font=("Helvetica Neue", 9), borderwidth=0)
        s.map("Right.TNotebook.Tab",
              background=[("selected", PALETTE["bg_card"])],
              foreground=[("selected", PALETTE["fg_primary"])])

    # ══════════════════════════════════════════════════════════════════════════
    #  UI construction (delegates to components)
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self) -> None:
        # 1. Status bar (packed to BOTTOM first so it's always visible)
        self._status_bar = StatusBar(self.root)

        # 2. Top bar
        self._top_bar = TopBar(
            self.root,
            callbacks={
                "open":               self._open_pdf,
                "save":               self._save_pdf,
                "save_as":            self._save_pdf_as,
                "undo":               self._undo,
                "redo":               self._redo,
                "zoom_in":            self._zoom_in,
                "zoom_out":           self._zoom_out,
                "zoom_reset":         self._zoom_reset,
                "zoom_fit_width":     self._zoom_fit_width,
                "zoom_fit_page":      self._zoom_fit_page,
                "set_single_mode":    self._set_single_mode,
                "set_continuous_mode":self._set_continuous_mode,
                "toggle_search_bar":  self._toggle_search_bar,
                "open_merge_split":   self._open_merge_split_dialog,
                "start_image_staging":self._start_image_staging,
                "wc_close":           self._wc_close,
                "wc_minimize":        self._wc_minimize,
                "wc_maximize":        self._wc_maximize,
            },
            has_merge_split=_HAS_MERGE_SPLIT,
        )

        # 3. Body row
        self._body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        self._body.pack(fill=tk.BOTH, expand=True)

        # 4. Icon toolbar (left)
        self._icon_toolbar = IconToolbar(
            self._body,
            on_tool_select=self._select_tool,
            page_action_callbacks={
                "rotate_left":  lambda: self._rotate(-90),
                "rotate_right": lambda: self._rotate(90),
                "add_page":     self._add_page,
                "delete_page":  self._delete_page,
                "ocr_page":     self._ocr_current_page,
            },
        )

        # 5. Right panel (thumbnails + properties)
        self._right_panel = RightPanel(
            self._body,
            get_doc=lambda: self.doc,
            get_current_page=lambda: self.current_page_idx,
            thumbnail_callbacks={
                "root":               self.root,
                "prev_page":          self._prev_page,
                "next_page":          self._next_page,
                "on_page_click":      self._thumb_page_click,
                "on_reorder":         self._thumb_reorder,
                "on_add_page":        self._thumb_add_page,
                "on_delete_page":     self._thumb_delete_page,
                "on_duplicate_page":  self._thumb_duplicate_page,
                "on_rotate_page":     self._thumb_rotate_page,
                "get_image_thumbnail":self._get_image_thumbnail,
            },
            tool_style_state=self._style,
            on_tool_style_change=self._on_tool_style_change,
        )

        # 6. Canvas area (centre, expands)
        self._canvas_area = CanvasArea(
            self._body,
            canvas_callbacks={
                "on_click":      self._on_canvas_click,
                "on_drag":       self._on_canvas_drag,
                "on_release":    self._on_canvas_release,
                "on_mousewheel": self._on_mousewheel,
                "on_ctrl_scroll":self._on_ctrl_scroll,
                "on_motion":     self._on_mouse_motion,
                "on_configure":  lambda e: self._render(),
            },
            search_bar_callbacks={
                "on_find":       self._search_bar_find,
                "on_next":       self._search_bar_next,
                "on_prev":       self._search_bar_prev,
                "on_redact_one": self._search_bar_redact_one,
                "on_redact_all": self._search_bar_redact_all,
                "on_close":      self._toggle_search_bar,
            },
        )

        # Convenience aliases used throughout
        self.canvas = self._canvas_area.canvas

        # Startup placeholder
        self._startup_frame = None
        self._update_view_mode_buttons()
        self._update_zoom_label()

    # ══════════════════════════════════════════════════════════════════════════
    #  Key bindings
    # ══════════════════════════════════════════════════════════════════════════

    def _bind_keys(self) -> None:
        r = self.root
        r.bind("<Control-o>",     lambda e: self._open_pdf())
        r.bind("<Control-s>",     lambda e: self._save_pdf())
        r.bind("<Control-S>",     lambda e: self._save_pdf_as())
        r.bind("<Control-z>",     lambda e: self._undo())
        r.bind("<Control-y>",     lambda e: self._redo())
        r.bind("<Control-equal>", lambda e: self._zoom_in())
        r.bind("<Control-minus>", lambda e: self._zoom_out())
        r.bind("<Control-0>",     lambda e: self._zoom_reset())
        r.bind("<Control-1>",     lambda e: self._zoom_fit_width())
        r.bind("<Control-2>",     lambda e: self._zoom_fit_page())
        r.bind("<Left>",          lambda e: self._prev_page())
        r.bind("<Right>",         lambda e: self._next_page())
        r.bind("<Escape>",        lambda e: self._on_escape())
        r.bind("<Control-c>",     lambda e: self._copy_selected_text())
        r.bind("<Control-f>",     lambda e: self._toggle_search_bar())
        r.bind("<F3>",            lambda e: self._search_bar_next())
        r.bind("<Shift-F3>",      lambda e: self._search_bar_prev())
        r.bind("<Control-t>",     lambda e: self._right_panel.toggle_visibility())
        r.bind("<KeyPress>",      self._on_key_press)

    def _on_key_press(self, event: tk.Event) -> None:
        focused = self.root.focus_get()
        if isinstance(focused, (tk.Entry, tk.Text)):
            return
        key = event.keysym.lower()
        if key in TOOL_KEY_MAP:
            tool = TOOL_KEY_MAP[key]
            self._select_tool(tool)
            self._flash_status(
                f"Tool: {tool.replace('_', ' ').title()}  [{key.upper()}]",
                color=PALETTE["accent_light"], duration_ms=1200,
            )

    # ══════════════════════════════════════════════════════════════════════════
    #  Tool management
    # ══════════════════════════════════════════════════════════════════════════

    def _init_tools(self) -> None:
        ctx = self._ctx
        s   = self._style
        self._tools["highlight"]    = AnnotationTool(
            ctx, self.annotation_service, "highlight",
            get_stroke_rgb=lambda: s["annot_stroke_rgb"],
            get_fill_rgb=lambda:   s["annot_fill_rgb"],
            get_width=lambda:      s["annot_width"],
        )
        self._tools["rect_annot"]   = AnnotationTool(
            ctx, self.annotation_service, "rect_annot",
            get_stroke_rgb=lambda: s["annot_stroke_rgb"],
            get_fill_rgb=lambda:   s["annot_fill_rgb"],
            get_width=lambda:      s["annot_width"],
        )
        self._tools["insert_image"] = ImageInsertTool(
            ctx, self.image_service, set_hint=lambda t: None)
        self._tools["extract"]      = ImageExtractTool(ctx, self.image_service)
        self._tools["select_text"]  = SelectTextTool(ctx, self.root)
        self._tools["redact"]       = RedactTool(
            ctx, self.redaction_service,
            get_fill_color=lambda:       s["redact_fill_color"],
            get_replacement_text=lambda: s["redact_label"],
            on_navigate_page=self._navigate_to,
            on_hit_changed=self._on_search_hit_changed,
        )
        self._tools["draw"]         = DrawTool(
            ctx,
            annotation_service=self.annotation_service,
            get_mode=lambda:       s["draw_mode"],
            get_stroke_rgb=lambda: s["draw_stroke_rgb"],
            get_fill_rgb=lambda:   s["draw_fill_rgb"],
            get_width=lambda:      s["draw_width"],
            get_opacity=lambda:    s["draw_opacity"],
            on_committed=self._on_draw_committed,
        )

    def _get_tool(self, name: str):
        return self._tools.get(name)

    def _select_tool(self, name: str) -> None:
        self._active_tool_name = name
        self._on_tool_change()

    def _on_tool_change(self) -> None:
        name = self._active_tool_name
        self._status_bar.set_tool(name)

        if self._current_tool is not None:
            self._current_tool.deactivate()

        if name != "redact":
            rt = self._get_tool("redact")
            if rt and rt.has_pending_hits:
                rt.cancel_hits()

        cursor_map = {
            "text": "crosshair", "insert_image": "crosshair",
            "highlight": "crosshair", "rect_annot": "crosshair",
            "select_text": "ibeam", "extract": "arrow",
            "redact": "crosshair", "draw": "crosshair",
        }
        self.canvas.config(cursor=cursor_map.get(name, "crosshair"))

        self._icon_toolbar.set_active_tool(name)
        self._right_panel.render_tool_props(name)
        self._right_panel.select_properties_tab()

        self._current_tool = self._get_tool(name)
        if self._current_tool:
            self._current_tool.activate()

    def _on_tool_state_change(self, key: str, value) -> None:
        """Route tool-state events (currently used by RedactTool)."""
        if key == "redact.hits_found":
            pass  # handled via on_hit_changed callback

    def _on_tool_style_change(self, key: str, value) -> None:
        """
        Called by RightPanel when the user changes a style value.
        Handles special compound keys (redact.find / redact.confirm / redact.cancel).
        """
        if key == "redact.find":
            self._redact_find_from_props(value)
        elif key == "redact.confirm":
            self._redact_confirm()
        elif key == "redact.cancel":
            self._redact_cancel_hits()
        # All other keys are already written directly into self._style by RightPanel.

    # ══════════════════════════════════════════════════════════════════════════
    #  Startup / welcome screen
    # ══════════════════════════════════════════════════════════════════════════

    def _show_startup_screen(self) -> None:
        if self.doc:
            return
        self._hide_startup_screen()
        frame = tk.Frame(self.canvas, bg=PALETTE["bg_dark"])
        self._startup_frame = frame
        inner = tk.Frame(frame, bg=PALETTE["bg_dark"])
        inner.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(inner, text="◼", bg=PALETTE["bg_dark"], fg=PALETTE["accent"],
                 font=("Helvetica Neue", 52)).pack(pady=(0, 4))
        tk.Label(inner, text="PDF Editor", bg=PALETTE["bg_dark"],
                 fg=PALETTE["fg_primary"],
                 font=("Helvetica Neue", 22, "bold")).pack()
        tk.Label(inner, text="Open a PDF file to get started",
                 bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"],
                 font=("Helvetica Neue", 10)).pack(pady=(4, 20))
        tk.Button(inner, text="  Open PDF…  ", command=self._open_pdf,
                  bg=PALETTE["accent"], fg=PALETTE["fg_inverse"],
                  activebackground=PALETTE["accent_light"],
                  activeforeground=PALETTE["fg_inverse"],
                  font=("Helvetica Neue", 12, "bold"),
                  relief="flat", bd=0, padx=28, pady=10,
                  cursor="hand2", highlightthickness=0).pack(pady=(0, 28))

        recents = self._recent.get()
        if recents:
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(0, 12))
            tk.Label(inner, text="RECENT FILES", bg=PALETTE["bg_dark"],
                     fg=PALETTE["fg_dim"],
                     font=("Helvetica Neue", 8, "bold")).pack(anchor="w", pady=(0, 6))
            for p in recents:
                row = tk.Frame(inner, bg=PALETTE["bg_dark"], cursor="hand2")
                row.pack(fill=tk.X, pady=1)
                name = os.path.basename(p)
                directory = os.path.dirname(p)
                if len(directory) > 48:
                    directory = "…" + directory[-46:]
                nl = tk.Label(row, text=name, bg=PALETTE["bg_dark"],
                              fg=PALETTE["fg_primary"],
                              font=("Helvetica Neue", 10), anchor="w", cursor="hand2")
                nl.pack(anchor="w")
                pl = tk.Label(row, text=directory, bg=PALETTE["bg_dark"],
                              fg=PALETTE["fg_dim"],
                              font=("Helvetica Neue", 8), anchor="w", cursor="hand2")
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
                    w.bind("<Enter>",    _enter)
                    w.bind("<Leave>",    _leave)
                    w.bind("<Button-1>", _click)
                tk.Frame(inner, bg=PALETTE["border"], height=1).pack(
                    fill=tk.X, pady=(4, 0))
        frame.place(x=0, y=0, relwidth=1, relheight=1)

    def _hide_startup_screen(self) -> None:
        if self._startup_frame:
            try:
                self._startup_frame.destroy()
            except Exception:
                pass
            self._startup_frame = None

    # ══════════════════════════════════════════════════════════════════════════
    #  Recent files
    # ══════════════════════════════════════════════════════════════════════════

    def _rebuild_recent_menu(self) -> None:
        menu = tk.Menu(
            self.root, tearoff=0,
            bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"],
            activebackground=PALETTE["accent_dim"],
            activeforeground=PALETTE["accent_light"],
            font=("Helvetica Neue", 9), relief="flat", bd=1,
        )
        recents = self._recent.get()
        if recents:
            for p in recents:
                label = os.path.basename(p)
                dirname = os.path.dirname(p)
                if len(dirname) > 40:
                    dirname = "…" + dirname[-38:]
                menu.add_command(
                    label=f"  {label}\n  {dirname}",
                    command=lambda fp=p: self._open_recent(fp),
                )
            menu.add_separator()
            menu.add_command(label="  Clear recent files",
                             command=self._clear_recent,
                             foreground=PALETTE["fg_dim"])
        else:
            menu.add_command(label="  No recent files", state="disabled")
        self._top_bar.set_recent_menu(menu)

    def _clear_recent(self) -> None:
        self._recent.clear()
        self._rebuild_recent_menu()
        if self._startup_frame:
            self._show_startup_screen()

    # ══════════════════════════════════════════════════════════════════════════
    #  File operations
    # ══════════════════════════════════════════════════════════════════════════

    def _open_pdf(self) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes", "You have unsaved changes.\nSave before opening?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        path = filedialog.askopenfilename(
            title="Open PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")])
        if path:
            self._open_pdf_path(path)

    def _open_pdf_path(self, path: str) -> None:
        self._is_staging_mode = False
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
        try:
            self.doc = PDFDocument(path)
        except Exception as ex:
            messagebox.showerror("Error", f"Could not open:\n{ex}")
            self._recent.remove(path)
            self._rebuild_recent_menu()
            return
        self.current_page_idx   = 0
        self._current_path      = path
        self._unsaved_changes   = False
        self._history.clear()
        self._cont_images.clear()
        self._recent.add(path)
        self._rebuild_recent_menu()
        self._hide_startup_screen()
        self._update_title()
        self._render()
        self._right_panel.thumb.reset()
        # Fit to width on open — deferred so the canvas has been laid out
        self.root.after(80, self._zoom_fit_width)

    def _open_recent(self, path: str) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes", "You have unsaved changes.\nSave before opening?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        self._open_pdf_path(path)

    def _save_pdf(self) -> bool:
        if self._is_staging_mode:
            return self._generate_pdf_from_staging()
        if not self.doc:
            return False
        if not self._current_path:
            return self._save_pdf_as()
        self._commit_all_boxes()
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
        if not self.doc:
            return False
        self._commit_all_boxes()
        path = filedialog.asksaveasfilename(
            title="Save PDF As", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=os.path.basename(self._current_path)
            if self._current_path else "document.pdf",
        )
        if not path:
            self._flash_status("Save cancelled", color=PALETTE["fg_secondary"])
            return False
        try:
            self.doc.save(path)
            self._current_path    = path
            self._unsaved_changes = False
            self.doc.path         = path
            self._history.mark_saved()
            self._update_title()
            self._flash_status(f"✓ Saved as {os.path.basename(path)}")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    # ══════════════════════════════════════════════════════════════════════════
    #  Staging mode (Images → PDF)
    # ══════════════════════════════════════════════════════════════════════════

    def _get_image_thumbnail(self, path: str, width: int) -> bytes:
        return self.image_conversion_service.get_image_thumbnail(path, width)

    def _start_image_staging(self) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes", "Save before continuing?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        paths = filedialog.askopenfilenames(
            title="Select Images to Combine into PDF",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if not paths:
            return
        self._commit_all_boxes()
        if self.doc:
            self.doc.close()
            self.doc = None
        self._staging_images  = list(paths)
        self._is_staging_mode = True
        self._current_path    = None
        self._update_title()
        self._right_panel.thumb.reset_for_images(self._staging_images)
        self._flash_status("Staging: drag thumbnails to reorder, then Save.")
        self._preview_staging_image(0)

    def _preview_staging_image(self, idx: int) -> None:
        if not self._is_staging_mode or idx >= len(self._staging_images):
            return
        self.current_page_idx = idx
        path = self._staging_images[idx]
        canvas_w  = self.canvas.winfo_width()
        preview_w = int(canvas_w * 0.8 * self.scale_factor)
        img_bytes = self._get_image_thumbnail(path, width=preview_w)
        if img_bytes:
            self.tk_image = tk.PhotoImage(data=img_bytes)
            self.canvas.delete("all")
            self.canvas.create_image(canvas_w // 2, 40, anchor=tk.N,
                                     image=self.tk_image, tags="page_img")
            self._right_panel.update_page_label(
                idx + 1, len(self._staging_images))
            self._status_bar.set_page_size("Image Preview")
            cb = tk.Checkbutton(
                self.canvas, text="Run OCR (make text selectable)",
                variable=self._staging_ocr_var,
                bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"],
                selectcolor=PALETTE["accent_dim"],
                activebackground=PALETTE["bg_hover"],
                highlightthickness=0)
            self.canvas.create_window(canvas_w // 2, 15, window=cb, tags="page_img")
            self._right_panel.thumb.refresh_all_borders()
            self._right_panel.thumb.scroll_to_active()

    def _exit_staging_mode(self) -> None:
        if not self._is_staging_mode:
            return
        self._is_staging_mode = False
        self._staging_images.clear()
        self.canvas.delete("all")
        self._right_panel.thumb.reset()
        self._show_startup_screen()
        self._flash_status("Cancelled", color=PALETTE["fg_secondary"])

    def _generate_pdf_from_staging(self) -> bool:
        if not self._staging_images:
            return False
        out_path = filedialog.asksaveasfilename(
            title="Save Generated PDF", defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile="Combined_Images.pdf")
        if not out_path:
            return False
        self.root.config(cursor="watch")
        self.root.update()
        cmd = ConvertImagesToPdfCommand(
            self.image_conversion_service, self._staging_images, out_path,
            apply_ocr=self._staging_ocr_var.get())
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

    # ══════════════════════════════════════════════════════════════════════════
    #  OCR
    # ══════════════════════════════════════════════════════════════════════════

    def _ocr_current_page(self) -> None:
        if not self.doc:
            return
        self.root.config(cursor="watch")
        self.root.update()
        cmd = OcrPageCommand(self.doc, self.current_page_idx)
        try:
            cmd.execute()
            self._push_history(cmd)
            self._flash_status("✓ OCR complete — text is now selectable.")
            sel = self._get_tool("select_text")
            if sel and self._active_tool_name == "select_text":
                sel.reload()
            self._render()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("OCR Error", str(ex))
        finally:
            self.root.config(cursor="")

    # ══════════════════════════════════════════════════════════════════════════
    #  Merge / Split
    # ══════════════════════════════════════════════════════════════════════════

    def _open_merge_split_dialog(self) -> None:
        if not _HAS_MERGE_SPLIT:
            return
        MergeSplitDialog(
            root=self.root, service=self.merge_split_service,
            current_doc=self.doc, on_open_path=self._open_pdf_path,
        )

    # ══════════════════════════════════════════════════════════════════════════
    #  Page management
    # ══════════════════════════════════════════════════════════════════════════

    def _prev_page(self) -> None:
        if self.doc and self.current_page_idx > 0:
            self._navigate_to(self.current_page_idx - 1)

    def _next_page(self) -> None:
        if self.doc and self.current_page_idx < self.doc.page_count - 1:
            self._navigate_to(self.current_page_idx + 1)

    def _navigate_to(self, idx: int) -> None:
        self._commit_all_boxes()
        if self._current_tool:
            self._current_tool.deactivate()
        self.current_page_idx = idx
        if self._continuous_mode:
            self._update_cont_offsets(idx)
            self._right_panel.thumb.refresh_all_borders()
            self._right_panel.thumb.scroll_to_active()
            self._scroll_to_current_cont()
            page = self.doc.get_page(idx)
            self._right_panel.update_page_label(idx + 1, self.doc.page_count)
            self._status_bar.set_page_size(
                f"{int(page.width)} × {int(page.height)} pt")
        else:
            self._right_panel.thumb.refresh_all_borders()
            self._render()
        if self._current_tool:
            self._current_tool.activate()

    def _thumb_page_click(self, idx: int) -> None:
        if self._is_staging_mode:
            self._preview_staging_image(idx)
        else:
            if not self.doc or idx == self.current_page_idx:
                return
            self._navigate_to(idx)

    def _thumb_reorder(self, src_idx: int, dst_idx: int) -> None:
        if self._is_staging_mode:
            if src_idx == dst_idx:
                return
            path = self._staging_images.pop(src_idx)
            insert_at = dst_idx if dst_idx < src_idx else dst_idx - 1
            insert_at = max(0, min(insert_at, len(self._staging_images)))
            self._staging_images.insert(insert_at, path)
            self._right_panel.thumb.reset_for_images(self._staging_images)
            self._preview_staging_image(insert_at)
            self._flash_status(f"↕ Moved image {src_idx+1} → {insert_at+1}")
            return
        if not self.doc or src_idx == dst_idx:
            return
        n = self.doc.page_count
        if not (0 <= src_idx < n) or not (0 <= dst_idx <= n):
            return
        order = list(range(n))
        order.pop(src_idx)
        insert_at = dst_idx if dst_idx < src_idx else dst_idx - 1
        insert_at = max(0, min(insert_at, len(order)))
        order.insert(insert_at, src_idx)
        if order == list(range(n)):
            return
        prev_page = self.current_page_idx
        cmd = ReorderPagesCommand(self.doc, order)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Reorder Error", str(ex))
            return
        try:
            self.current_page_idx = order.index(prev_page)
        except ValueError:
            self.current_page_idx = 0
        self._mark_dirty()
        self._cont_images.clear()
        self._right_panel.thumb.reset()
        self._render()
        self._push_history(cmd)
        self._flash_status(f"↕ Moved page {src_idx+1} → {insert_at+1}")

    def _thumb_add_page(self, after_idx: int) -> None:
        if not self.doc:
            return
        try:
            ref = self.doc.get_page(max(0, after_idx))
            self.doc.insert_page(after_idx + 1, width=ref.width, height=ref.height)
        except Exception as ex:
            messagebox.showerror("Add Page", str(ex))
            return
        self.current_page_idx = after_idx + 1
        self._mark_dirty()
        self._cont_images.clear()
        self._right_panel.thumb.reset()
        self._render()
        self._flash_status(f"+ Added page at {after_idx+2}")

    def _thumb_delete_page(self, idx: int) -> None:
        if not self.doc:
            return
        if self.doc.page_count <= 1:
            messagebox.showwarning("Cannot Delete",
                                   "A PDF must have at least one page.")
            return
        if not messagebox.askyesno("Delete Page",
                                   f"Permanently delete page {idx+1}?",
                                   icon="warning"):
            return
        try:
            self.doc.delete_page(idx)
        except Exception as ex:
            messagebox.showerror("Delete", str(ex))
            return
        self.current_page_idx = min(self.current_page_idx, self.doc.page_count - 1)
        self._mark_dirty()
        self._cont_images.clear()
        self._right_panel.thumb.reset()
        self._render()
        self._flash_status(f"✕ Deleted page {idx+1}")

    def _thumb_duplicate_page(self, idx: int) -> None:
        if not self.doc:
            return
        cmd = DuplicatePageCommand(self.doc, idx)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Duplicate", str(ex))
            return
        self._push_history(cmd)
        self.current_page_idx = idx + 1
        self._mark_dirty()
        self._cont_images.clear()
        self._right_panel.thumb.reset()
        self._render()
        self._flash_status(f"⧉ Duplicated page {idx+1}")

    def _thumb_rotate_page(self, idx: int, angle: int) -> None:
        if not self.doc:
            return
        cmd = RotatePageCommand(self.page_service, self.doc, idx, angle)
        try:
            cmd.execute()
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Rotate", str(ex))
            return
        self._push_history(cmd)
        self._right_panel.thumb.mark_dirty(idx)
        self._cont_invalidate_cache(idx)
        if idx == self.current_page_idx:
            self._render()
        self._flash_status(
            f"{'↺' if angle < 0 else '↻'} Rotated page {idx+1}")

    def _rotate(self, angle: int) -> None:
        if self.doc:
            self._thumb_rotate_page(self.current_page_idx, angle)

    def _add_page(self) -> None:
        if self.doc:
            self._thumb_add_page(self.current_page_idx)

    def _delete_page(self) -> None:
        if self.doc:
            self._thumb_delete_page(self.current_page_idx)

    # ══════════════════════════════════════════════════════════════════════════
    #  Zoom
    # ══════════════════════════════════════════════════════════════════════════

    def _zoom_in(self) -> None:
        self._set_zoom(min(MAX_SCALE, self.scale_factor + SCALE_STEP))

    def _zoom_out(self) -> None:
        self._set_zoom(max(MIN_SCALE, self.scale_factor - SCALE_STEP))

    def _zoom_reset(self) -> None:
        self._set_zoom(RENDER_DPI)

    def _zoom_fit_width(self) -> None:
        """Scale so the current page fills the canvas width."""
        if not self.doc:
            return
        page = self.doc.get_page(self.current_page_idx)
        cw = self.canvas.winfo_width()
        if cw < 10:
            # Canvas not yet realised — retry once it is
            self.root.after(60, self._zoom_fit_width)
            return
        available_w = cw - 2 * PAD_XL
        new_scale = round(
            max(MIN_SCALE, min(MAX_SCALE, available_w / page.width)), 3
        )
        self.scale_factor = new_scale
        self._update_zoom_label()
        self._cont_invalidate_cache()
        self._render()
        self._flash_status("↔ Fit width", color=PALETTE["accent_light"], duration_ms=1200)

    def _zoom_fit_page(self) -> None:
        """Scale so the current page fits entirely within the canvas."""
        if not self.doc:
            return
        page = self.doc.get_page(self.current_page_idx)
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw < 10 or ch < 10:
            self.root.after(60, self._zoom_fit_page)
            return
        scale_w = (cw - 2 * PAD_XL) / page.width
        scale_h = (ch - 2 * PAD_XL) / page.height
        new_scale = round(
            max(MIN_SCALE, min(MAX_SCALE, min(scale_w, scale_h))), 3
        )
        self.scale_factor = new_scale
        self._update_zoom_label()
        self._cont_invalidate_cache()
        self._render()
        self._flash_status("⛶ Fit page", color=PALETTE["accent_light"], duration_ms=1200)

    def _set_zoom(self, s: float) -> None:
        self.scale_factor = round(s, 3)
        self._update_zoom_label()
        self._cont_invalidate_cache()
        self._render()

    def _update_zoom_label(self) -> None:
        pct = int(self.scale_factor / RENDER_DPI * 100)
        self._top_bar.set_zoom_label(f"{pct}%")
        self._status_bar.set_zoom(f"Zoom {pct}%")

    # ══════════════════════════════════════════════════════════════════════════
    #  View mode
    # ══════════════════════════════════════════════════════════════════════════

    def _set_single_mode(self) -> None:
        if not self._continuous_mode:
            return
        self._commit_all_boxes()
        self._continuous_mode = False
        self._cont_images.clear()
        self._update_view_mode_buttons()
        self._render()

    def _set_continuous_mode(self) -> None:
        if self._continuous_mode:
            return
        self._commit_all_boxes()
        self._continuous_mode = True
        self._update_view_mode_buttons()
        self._render()
        self.root.after(80, self._scroll_to_current_cont)

    def _update_view_mode_buttons(self) -> None:
        self._top_bar.update_view_mode_buttons(self._continuous_mode)

    # ══════════════════════════════════════════════════════════════════════════
    #  Search bar
    # ══════════════════════════════════════════════════════════════════════════

    def _toggle_search_bar(self) -> None:
        if self._canvas_area.search_bar_visible:
            self._canvas_area.hide_search_bar()
            self._search_bar_clear()
        else:
            self._canvas_area.show_search_bar()
            if self._active_tool_name != "redact":
                self._select_tool("redact")

    def _search_bar_find(self) -> None:
        if not self.doc:
            return
        query = self._canvas_area.search_query
        if not query:
            return
        if self._active_tool_name != "redact":
            self._select_tool("redact")
        rt = self._get_tool("redact")
        if not rt:
            return
        total = rt.search_all_pages(
            query, case_sensitive=self._canvas_area.search_case_sensitive)
        if total == 0:
            self._canvas_area.update_hit_display(-1, 0)
            self._flash_status(
                f'No matches for "{query}"', color=PALETTE["fg_secondary"])

    def _search_bar_next(self) -> None:
        rt = self._get_tool("redact")
        if rt:
            rt.navigate_next()

    def _search_bar_prev(self) -> None:
        rt = self._get_tool("redact")
        if rt:
            rt.navigate_prev()

    def _search_bar_redact_one(self) -> None:
        rt = self._get_tool("redact")
        if rt:
            rt.redact_current_hit()
        self._right_panel.hide_redact_confirm()

    def _search_bar_redact_all(self) -> None:
        rt = self._get_tool("redact")
        if rt:
            rt.redact_all_hits()
        self._right_panel.hide_redact_confirm()

    def _search_bar_clear(self) -> None:
        rt = self._get_tool("redact")
        if rt and rt.has_search_hits:
            rt.cancel_search()
        self._canvas_area.clear_hit_display()

    def _on_search_hit_changed(self, cur_idx: int, total: int) -> None:
        if total == 0 or cur_idx < 0:
            self._canvas_area.update_hit_display(-1, 0)
            return
        rt = self._get_tool("redact")
        page_lbl = (f"p.{rt._all_hits[cur_idx][0]+1}" if rt else "")
        self._canvas_area.update_hit_display(cur_idx, total, page_lbl)
        self._right_panel.show_redact_confirm(total)

    def _redact_find_from_props(self, params: dict) -> None:
        rt = self._get_tool("redact")
        if not rt or not self.doc:
            return
        query = params.get("query", "")
        if not query:
            self._flash_status("Enter a search term first",
                               color=PALETTE["fg_secondary"])
            return
        total = rt.search_all_pages(
            query, case_sensitive=params.get("case_sensitive", False))
        if total == 0:
            self._right_panel.hide_redact_confirm()
            self._flash_status(
                f'No matches for "{query}"', color=PALETTE["fg_secondary"])

    def _redact_confirm(self) -> None:
        rt = self._get_tool("redact")
        if rt:
            rt.redact_all_hits()
        self._right_panel.hide_redact_confirm()
        self._canvas_area.clear_hit_display()

    def _redact_cancel_hits(self) -> None:
        rt = self._get_tool("redact")
        if rt:
            rt.cancel_search()
        self._right_panel.hide_redact_confirm()
        self._canvas_area.clear_hit_display()
        self._flash_status("Redaction cancelled",
                           color=PALETTE["fg_secondary"])

    def _on_draw_committed(self, page_idx: int, xref: int) -> None:
        cmd = DrawAnnotationCommand(self.doc, page_idx, xref)
        self._push_history(cmd)
        self._mark_dirty()
        self._cont_invalidate_cache(page_idx)
        self._right_panel.thumb.mark_dirty(page_idx)
        if page_idx == self.current_page_idx:
            self._render()
        elif self._continuous_mode:
            self._render_cont_page_refresh(page_idx)

    # ══════════════════════════════════════════════════════════════════════════
    #  Rendering
    # ══════════════════════════════════════════════════════════════════════════

    def _render(self) -> None:
        if not self.doc:
            return
        if self._continuous_mode:
            self._render_continuous()
        else:
            self._render_single()

    def _render_single(self) -> None:
        page = self.doc.get_page(self.current_page_idx)
        ppm  = page.render_to_ppm(scale=self.scale_factor)
        self.tk_image = self._make_page_image(ppm, self.current_page_idx)
        iw = int(page.width  * self.scale_factor)
        ih = int(page.height * self.scale_factor)
        cw = self.canvas.winfo_width()
        self._page_offset_x = max(PAD_XL, (cw - iw) // 2)
        self._page_offset_y = PAD_XL
        ox, oy = self._page_offset_x, self._page_offset_y
        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")
        self.canvas.delete("page_bg")
        self.canvas.delete("textsel")
        self.canvas.create_rectangle(
            ox+4, oy+4, ox+iw+4, oy+ih+4,
            fill=PALETTE["page_shadow"], outline="",
            stipple="gray25", tags="page_shadow")
        self.canvas.create_image(
            ox, oy, anchor=tk.NW, image=self.tk_image, tags="page_img")
        self.canvas.config(scrollregion=(0, 0, ox+iw+50, oy+ih+50))
        self._right_panel.update_page_label(
            self.current_page_idx + 1, self.doc.page_count)
        self._status_bar.set_page_size(
            f"{int(page.width)} × {int(page.height)} pt")
        for box in list(self._text_boxes):
            box.rescale(self.scale_factor, self._page_offset_x, self._page_offset_y)
        self._right_panel.thumb.refresh_all_borders()
        self._right_panel.thumb.scroll_to_active()

    _CONT_GAP = 20

    def _cont_page_top(self, idx: int) -> int:
        doc = self.doc
        if not doc:
            return 0
        y = self._CONT_GAP
        for i in range(idx):
            p  = doc.get_page(i)
            ih = int(p.height * self.scale_factor)
            y += ih + self._CONT_GAP
        return y

    def _cont_page_at_y(self, canvas_y: float) -> int:
        doc = self.doc
        if not doc:
            return 0
        y = self._CONT_GAP
        for i in range(doc.page_count):
            p  = doc.get_page(i)
            ih = int(p.height * self.scale_factor)
            if canvas_y <= y + ih:
                return i
            y += ih + self._CONT_GAP
        return doc.page_count - 1

    def _render_continuous(self) -> None:
        if self._cont_after_id:
            self.root.after_cancel(self._cont_after_id)
            self._cont_after_id = None
        doc = self.doc
        n   = doc.page_count
        cw  = self.canvas.winfo_width()
        total_h = self._CONT_GAP
        max_iw  = 0
        heights, widths = [], []
        for i in range(n):
            p  = doc.get_page(i)
            iw = int(p.width  * self.scale_factor)
            ih = int(p.height * self.scale_factor)
            heights.append(ih)
            widths.append(iw)
            max_iw = max(max_iw, iw)
            total_h += ih + self._CONT_GAP
        self.canvas.delete("page_img")
        self.canvas.delete("page_shadow")
        self.canvas.delete("page_bg")
        self.canvas.delete("textsel")
        self.canvas.config(
            scrollregion=(0, 0, max(cw, max_iw + 80), total_h))
        y = self._CONT_GAP
        for i in range(n):
            iw, ih = widths[i], heights[i]
            ox = max(PAD_XL, (cw - iw) // 2)
            self.canvas.create_rectangle(
                ox, y, ox+iw, y+ih,
                fill=PALETTE.get("page_bg", "#FFFFFF"), outline="",
                tags=("page_bg", f"page_bg_{i}"))
            self.canvas.create_rectangle(
                ox+4, y+4, ox+iw+4, y+ih+4,
                fill=PALETTE["page_shadow"], outline="", stipple="gray25",
                tags=("page_shadow", f"page_shadow_{i}"))
            self.canvas.tag_lower(f"page_shadow_{i}", f"page_bg_{i}")
            y += ih + self._CONT_GAP
        self._update_cont_offsets(self.current_page_idx)
        cur   = self.current_page_idx
        order = [cur]
        for delta in range(1, n):
            if cur - delta >= 0: order.append(cur - delta)
            if cur + delta < n:  order.append(cur + delta)

        def _render_one(remaining):
            if not remaining or not self.doc:
                self._cont_after_id = None
                return
            idx  = remaining[0]
            rest = remaining[1:]
            self._render_cont_page(idx, widths[idx], heights[idx], cw)
            self._cont_after_id = self.root.after_idle(
                lambda: _render_one(rest))

        _render_one(order)
        cur_page = doc.get_page(self.current_page_idx)
        self._right_panel.update_page_label(
            self.current_page_idx + 1, n)
        self._status_bar.set_page_size(
            f"{int(cur_page.width)} × {int(cur_page.height)} pt")
        self._right_panel.thumb.refresh_all_borders()
        self._right_panel.thumb.scroll_to_active()

    def _render_cont_page(self, idx: int, iw: int, ih: int, cw: int) -> None:
        doc = self.doc
        if not doc or idx >= doc.page_count:
            return
        key = (idx, self.scale_factor)
        if key not in self._cont_images:
            try:
                page = doc.get_page(idx)
                ppm  = page.render_to_ppm(scale=self.scale_factor)
                self._cont_images[key] = self._make_page_image(ppm, idx)
            except Exception:
                return
        img = self._cont_images[key]
        y   = self._cont_page_top(idx)
        ox  = max(PAD_XL, (cw - iw) // 2)
        self.canvas.delete(f"page_img_{idx}")
        self.canvas.create_image(
            ox, y, anchor=tk.NW, image=img,
            tags=("page_img", f"page_img_{idx}"))
        self.canvas.tag_lower(f"page_bg_{idx}", f"page_img_{idx}")
    
    def _make_page_image(self, ppm: bytes, page_idx: int) -> tk.PhotoImage:
        """
        Convert raw PPM bytes to a tk.PhotoImage, compositing both 
        text-selection and search hit highlight rectangles into the pixel data.
        """
        layers = []
        
        # 1. Text selection tool
        sel = self._get_tool("select_text")
        if sel:
            sel_rects = sel.get_highlight_rects_for_page(page_idx)
            if sel_rects:
                layers.append({
                    "rects": sel_rects, 
                    "color": (74, 144, 217), 
                    "alpha": 0.35
                })

        # 2. Search / Find / Redact tool hits
        rt = self._get_tool("redact")
        if rt and getattr(rt, "has_search_hits", False):
            if hasattr(rt, "get_highlight_rects_for_page"):
                active, inactive = rt.get_highlight_rects_for_page(page_idx)
                if inactive:
                    layers.append({
                        "rects": inactive, 
                        "color": (123, 63, 191), # Purple for inactive hits
                        "alpha": 0.45
                    })
                if active:
                    layers.append({
                        "rects": active, 
                        "color": (255, 184, 0), # Yellow/Orange for the current hit
                        "alpha": 0.65
                    })

        return composite_selection(
            ppm_bytes=ppm,
            scale=self.scale_factor,
            layers=layers
        )

    def _render_cont_page_refresh(self, page_idx: int) -> None:
        if not self.doc or not self._continuous_mode:
            return
        p  = self.doc.get_page(page_idx)
        iw = int(p.width  * self.scale_factor)
        ih = int(p.height * self.scale_factor)
        cw = self.canvas.winfo_width()
        self._render_cont_page(page_idx, iw, ih, cw)

    def _update_cont_offsets(self, idx: int) -> None:
        doc = self.doc
        if not doc:
            return
        p   = doc.get_page(idx)
        iw  = int(p.width * self.scale_factor)
        cw  = self.canvas.winfo_width()
        self._page_offset_x = max(PAD_XL, (cw - iw) // 2)
        self._page_offset_y = self._cont_page_top(idx)

    def _cont_invalidate_cache(self, page_idx: int | None = None) -> None:
        if page_idx is None:
            self._cont_images.clear()
        else:
            for k in [k for k in self._cont_images if k[0] == page_idx]:
                del self._cont_images[k]

    def _on_cont_scroll(self) -> None:
        self._scroll_after_id = None
        if not self.doc or not self._continuous_mode:
            return
        top    = self.canvas.canvasy(0)
        bottom = self.canvas.canvasy(self.canvas.winfo_height())
        mid    = (top + bottom) / 2
        idx    = self._cont_page_at_y(mid)
        if idx != self.current_page_idx:
            self.current_page_idx = idx
            self._update_cont_offsets(idx)
            page = self.doc.get_page(idx)
            self._right_panel.update_page_label(idx + 1, self.doc.page_count)
            self._status_bar.set_page_size(
                f"{int(page.width)} × {int(page.height)} pt")
            self._right_panel.thumb.refresh_all_borders()
            self._right_panel.thumb.scroll_to_active()

    def _scroll_to_current_cont(self) -> None:
        if not self.doc:
            return
        y_top   = self._cont_page_top(self.current_page_idx)
        total_h = self._cont_page_top(self.doc.page_count)
        if total_h > 0:
            frac = max(0.0, (y_top - self._CONT_GAP) / total_h)
            self.canvas.yview_moveto(frac)

    # ══════════════════════════════════════════════════════════════════════════
    #  Canvas event handlers
    # ══════════════════════════════════════════════════════════════════════════

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        if self._continuous_mode:
            idx = self._cont_page_at_y(cy)
            if idx != self.current_page_idx:
                self.current_page_idx = idx
                self._update_cont_offsets(idx)
                self._right_panel.thumb.refresh_all_borders()
                self._right_panel.thumb.scroll_to_active()
                page = self.doc.get_page(idx)
                self._right_panel.update_page_label(
                    idx + 1, self.doc.page_count)
        return (
            (cx - self._page_offset_x) / self.scale_factor,
            (cy - self._page_offset_y) / self.scale_factor,
        )

    def _on_canvas_click(self, event: tk.Event) -> None:
        if not self.doc:
            return
        if self._suppress_next_click:
            self._suppress_next_click = False
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        if self._active_tool_name == "text":
            pdf_x, pdf_y = self._canvas_to_pdf(cx, cy)
            self._spawn_textbox(pdf_x, pdf_y)
        else:
            t = self._get_tool(self._active_tool_name)
            if t:
                t.on_click(cx, cy)

    def _on_canvas_drag(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        t  = self._get_tool(self._active_tool_name)
        if t:
            t.on_drag(cx, cy)

    def _on_canvas_release(self, event: tk.Event) -> None:
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        t  = self._get_tool(self._active_tool_name)
        if t:
            t.on_release(cx, cy)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(1, "units")
        else:
            self.canvas.yview_scroll(-1 * (event.delta // 120), "units")
        if self._continuous_mode:
            if self._scroll_after_id:
                self.root.after_cancel(self._scroll_after_id)
            self._scroll_after_id = self.root.after(80, self._on_cont_scroll)

    def _on_ctrl_scroll(self, event: tk.Event) -> None:
        if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
            self._zoom_in()
        else:
            self._zoom_out()

    def _on_mouse_motion(self, event: tk.Event) -> None:
        if not self.doc:
            return
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        px, py = self._canvas_to_pdf(cx, cy)
        self._status_bar.set_coords(px, py)
        if self._active_tool_name == "select_text":
            t = self._get_tool("select_text")
            if t:
                t.on_motion(cx, cy)

    # ══════════════════════════════════════════════════════════════════════════
    #  Text box lifecycle
    # ══════════════════════════════════════════════════════════════════════════

    def _spawn_textbox(self, pdf_x: float, pdf_y: float) -> None:
        page  = self.doc.get_page(self.current_page_idx)
        pdf_w = page.width * 0.42
        pdf_h = self._style["fontsize"] * 4
        bg    = self._sample_page_color(pdf_x, pdf_y)
        box   = TextBox(
            canvas=self.canvas,
            pdf_x=pdf_x, pdf_y=pdf_y,
            pdf_w=pdf_w, pdf_h=pdf_h,
            scale=self.scale_factor,
            page_offset_x=self._page_offset_x,
            page_offset_y=self._page_offset_y,
            font_index=self._style["font_index"],
            fontsize=self._style["fontsize"],
            color_rgb=self._style["text_color"],
            entry_bg=bg,
            align=self._style["text_align"],
            on_commit=self._on_box_confirmed,
            on_delete=self._on_box_deleted,
            on_interact=self._on_box_interact,
        )
        self._text_boxes.append(box)

    def _sample_page_color(self, pdf_x: float, pdf_y: float) -> str:
        if self.tk_image is None:
            return self.canvas.cget("bg")
        try:
            ix = int(pdf_x * self.scale_factor)
            iy = int(pdf_y * self.scale_factor)
            r, g, b = self.tk_image.get(ix, iy)
            return f"#{r:02x}{g:02x}{b:02x}"
        except Exception:
            return self.canvas.cget("bg")

    def _on_box_confirmed(self, box: TextBox) -> None:
        self._text_boxes = [b for b in self._text_boxes if b is not box]
        text = box.get_text()
        if not text:
            return
        rect = (box.pdf_x, box.pdf_y,
                box.pdf_x + box.pdf_w, box.pdf_y + box.pdf_h)
        cmd  = InsertTextBoxCommand(
            self.text_service, self.doc,
            self.current_page_idx, rect, text,
            box.fontsize, box.pdf_font_name, box.pdf_color, box.align,
        )
        try:
            cmd.execute()
            self._push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Insert Error", str(ex))
            return
        self._render()

    def _on_box_interact(self) -> None:
        self._suppress_next_click = True

    def _on_box_deleted(self, box: TextBox) -> None:
        self._text_boxes = [b for b in self._text_boxes if b is not box]

    def _commit_all_boxes(self) -> None:
        for box in list(self._text_boxes):
            box._confirm()
        self._text_boxes.clear()

    def _dismiss_boxes(self) -> None:
        for box in list(self._text_boxes):
            box._delete()
        self._text_boxes.clear()

    def _copy_selected_text(self) -> None:
        t = self._get_tool("select_text")
        if t:
            t.copy()

    # ══════════════════════════════════════════════════════════════════════════
    #  History
    # ══════════════════════════════════════════════════════════════════════════

    def _push_history(self, cmd) -> None:
        self._history.push(cmd)
        self._right_panel.thumb.mark_dirty(self.current_page_idx)
        self._cont_invalidate_cache(self.current_page_idx)

    def _on_history_change(self) -> None:
        self._mark_dirty()

    def _undo(self) -> None:
        if not self._history.can_undo:
            self._flash_status("Nothing to undo", color=PALETTE["fg_secondary"])
            return
        try:
            cmd   = self._history._history[self._history._idx]
            label = self._history.undo()
            self._after_history_step(cmd)
            self._flash_status(f"↩ Undid {label}")
        except Exception as ex:
            messagebox.showerror("Undo Error", str(ex))

    def _redo(self) -> None:
        if not self._history.can_redo:
            self._flash_status("Nothing to redo", color=PALETTE["fg_secondary"])
            return
        try:
            cmd   = self._history._history[self._history._idx + 1]
            label = self._history.redo()
            self._after_history_step(cmd)
            self._flash_status(f"↪ Redid {label}")
        except Exception as ex:
            messagebox.showerror("Redo Error", str(ex))

    def _after_history_step(self, cmd) -> None:
        is_reorder = isinstance(cmd, (ReorderPagesCommand, DuplicatePageCommand))
        if is_reorder or cmd is None:
            n = self.doc.page_count if self.doc else 0
            self.current_page_idx = max(0, min(self.current_page_idx, n - 1))
            self._cont_images.clear()
            self._right_panel.thumb.reset()
        else:
            self._right_panel.thumb.mark_dirty(self.current_page_idx)
            self._cont_invalidate_cache(self.current_page_idx)
        self._render()

    # ══════════════════════════════════════════════════════════════════════════
    #  Status, title, dirty tracking
    # ══════════════════════════════════════════════════════════════════════════

    def _flash_status(
        self,
        message: str,
        color: str | None = None,
        duration_ms: int = 3000,
    ) -> None:
        self._status_bar.flash(message, color=color, duration_ms=duration_ms)

    def _update_title(self) -> None:
        if self._current_path:
            name   = os.path.basename(self._current_path)
            marker = " •" if self._unsaved_changes else ""
            title  = f"{name}{marker}"
        else:
            title = "PDF Editor" + (
                " — Untitled •" if self._unsaved_changes else "")
        self.root.title(
            f"PDF Editor — {title}" if self._current_path else title)
        self._top_bar.set_title(
            os.path.basename(self._current_path) +
            (" •" if self._unsaved_changes else "")
            if self._current_path else "PDF Editor"
        )

    def _mark_dirty(self) -> None:
        if not self._unsaved_changes:
            self._unsaved_changes = True
            self._update_title()

    # ══════════════════════════════════════════════════════════════════════════
    #  Window chrome helpers
    # ══════════════════════════════════════════════════════════════════════════

    def _wc_close(self) -> None:    self._on_closing()
    def _wc_minimize(self) -> None: self.root.iconify()
    def _wc_maximize(self) -> None: self.root.state("zoomed")

    # ══════════════════════════════════════════════════════════════════════════
    #  Escape / closing
    # ══════════════════════════════════════════════════════════════════════════

    def _on_escape(self) -> None:
        if self._canvas_area.search_bar_visible:
            self._toggle_search_bar()
        elif self._is_staging_mode:
            self._exit_staging_mode()
        else:
            self._dismiss_boxes()

    def _on_closing(self) -> None:
        if self._unsaved_changes:
            ans = messagebox.askyesnocancel(
                "Unsaved Changes", "Save before closing?")
            if ans is None:
                return
            if ans and not self._save_pdf():
                return
        self._commit_all_boxes()
        if self._current_tool:
            self._current_tool.deactivate()
        if (self._right_panel.thumb and
                hasattr(self._right_panel.thumb, "_after_id") and
                self._right_panel.thumb._after_id):
            self.root.after_cancel(self._right_panel.thumb._after_id)
        self._history.clear()
        if self.doc:
            self.doc.close()
        self.root.destroy()

    # ══════════════════════════════════════════════════════════════════════════
    #  AppContext properties (read by tools via ctx)
    # ══════════════════════════════════════════════════════════════════════════

    @property
    def _page_offset_x(self) -> float:
        return self.__page_offset_x

    @_page_offset_x.setter
    def _page_offset_x(self, v: float) -> None:
        self.__page_offset_x = v

    @property
    def _page_offset_y(self) -> float:
        return self.__page_offset_y

    @_page_offset_y.setter
    def _page_offset_y(self, v: float) -> None:
        self.__page_offset_y = v


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    InteractivePDFEditor(root)
    root.mainloop()