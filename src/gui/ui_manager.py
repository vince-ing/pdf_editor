# src/gui/ui_manager.py
from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Any

from src.gui.theme import PALETTE, PAD_M

from src.gui.components.top_bar      import TopBar
from src.gui.components.icon_toolbar import IconToolbar
from src.gui.components.right_panel  import RightPanel
from src.gui.components.canvas_area  import CanvasArea
from src.gui.components.status_bar   import StatusBar

class UIManager:
    def __init__(self, root: tk.Tk, app: Any, has_merge_split: bool):
        self.root = root
        self.app = app
        self.has_merge_split = has_merge_split
        
        self._apply_ttk_style()
        self.status_bar = StatusBar(self.root)
        self.top_bar: TopBar = None
        self.body: tk.Frame = None
        self.icon_toolbar: IconToolbar = None
        self.right_panel: RightPanel = None
        self.canvas_area: CanvasArea = None
        self.startup_frame = None

        self._build_components()

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

    def _build_components(self) -> None:
        app = self.app
        self.top_bar = TopBar(
            self.root,
            callbacks={
                "open": lambda: app.document_controller.open_pdf(), "save": lambda: app.document_controller.save_pdf(), "save_as": lambda: app.document_controller.save_pdf_as(),
                "ocr_page": lambda: app.ocr_controller.ocr_current_page(), "ocr_all_pages": lambda: app.ocr_controller.ocr_all_pages(),
                "tts_page": lambda: app.tts_controller.read_page(), "tts_all": lambda: app.tts_controller.read_all(), "tts_selection": lambda: app.tts_controller.read_selection(),
                "start_image_staging": lambda: app.document_controller.start_image_staging(), "open_merge_split": lambda: app.document_controller.open_merge_split_dialog(),
                "rotate_left": lambda: app.thumbnail_controller.rotate_page(app.viewport.current_page_idx, -90),
                "rotate_right": lambda: app.thumbnail_controller.rotate_page(app.viewport.current_page_idx, 90),
                "add_page": lambda: app.thumbnail_controller.add_page(app.viewport.current_page_idx), "delete_page": lambda: app.thumbnail_controller.delete_page(app.viewport.current_page_idx), 
                "undo": lambda: app.history_controller.undo(), "redo": lambda: app.history_controller.redo(),
                "zoom_in": lambda: app.viewport.zoom_in(), "zoom_out": lambda: app.viewport.zoom_out(), "zoom_reset": lambda: app.viewport.zoom_reset(),
                "zoom_fit_width": lambda: app.viewport.zoom_fit_width(), "zoom_fit_page": lambda: app.viewport.zoom_fit_page(),
                "set_single_mode": lambda: self.set_single_mode(), "set_continuous_mode": lambda: self.set_continuous_mode(),
                "toggle_search_bar": lambda: self.toggle_search_bar(), "toggle_inspector": lambda: self.toggle_inspector(),
                "wc_close": lambda: app.window_controller.close(), "wc_minimize": lambda: app.window_controller.minimize(), "wc_maximize": lambda: app.window_controller.maximize(),
            },
            has_merge_split=self.has_merge_split,
        )

        self.body = tk.Frame(self.root, bg=PALETTE["bg_dark"])
        self.body.pack(fill=tk.BOTH, expand=True)

        self.icon_toolbar = IconToolbar(
            self.body, 
            on_tool_select=lambda t: app.tool_manager.select_tool(t),
            page_action_callbacks={
                "rotate_left": lambda: app.thumbnail_controller.rotate_page(app.viewport.current_page_idx, -90), "rotate_right": lambda: app.thumbnail_controller.rotate_page(app.viewport.current_page_idx, 90),
                "add_page": lambda: app.thumbnail_controller.add_page(app.viewport.current_page_idx), "delete_page": lambda: app.thumbnail_controller.delete_page(app.viewport.current_page_idx),
                "ocr_page": lambda: app.ocr_controller.ocr_current_page()
            },
        )

        self.right_panel = RightPanel(
            self.body, get_doc=lambda: app.doc, get_current_page=lambda: app.viewport.current_page_idx,
            thumbnail_callbacks={
                "root": self.root, "page_click": lambda idx: app.thumbnail_controller.page_click(idx), "reorder": lambda s, d: app.thumbnail_controller.reorder(s, d),
                "add_page": lambda idx: app.thumbnail_controller.add_page(idx), "delete_page": lambda idx: app.thumbnail_controller.delete_page(idx), 
                "duplicate_page": lambda idx: app.thumbnail_controller.duplicate_page(idx), "rotate_page": lambda idx, angle: app.thumbnail_controller.rotate_page(idx, angle), 
                "prev_page": lambda: app._prev_page(), "next_page": lambda: app._next_page(), "on_page_jump": lambda n: app._on_page_jump(n),
            },
            tool_style_state=lambda: app.tool_manager.style,  # ← lazy lambda, not eager access
            on_tool_style_change=lambda k, v: app.tool_manager.on_tool_style_change(k, v),
            toc_callbacks={"on_navigate": lambda p: app._toc_navigate(p), "on_toc_changed": lambda toc: app._toc_changed(toc), "get_page_count": lambda: app.doc.page_count if app.doc else 0},
        )

        self.canvas_area = CanvasArea(
            self.body,
            canvas_callbacks={
                "on_click": lambda e: app.tool_manager.handle_click(self.canvas_area.canvas.canvasx(e.x), self.canvas_area.canvas.canvasy(e.y)),
                "on_drag": lambda e: app.tool_manager.handle_drag(self.canvas_area.canvas.canvasx(e.x), self.canvas_area.canvas.canvasy(e.y)),
                "on_release": lambda e: app.tool_manager.handle_release(self.canvas_area.canvas.canvasx(e.x), self.canvas_area.canvas.canvasy(e.y)),
                "on_mousewheel": lambda e: self._on_mousewheel(e), "on_ctrl_scroll": lambda e: app.viewport.on_ctrl_scroll(e) if hasattr(app, 'viewport') else None,
                "on_motion": lambda e: self._on_mouse_motion(e), "on_configure": lambda e: self._on_canvas_configure(e), "on_scroll_changed": lambda: app.viewport.on_canvas_scrolled() if hasattr(app, 'viewport') else None,
            },
            search_bar_callbacks={
                "on_find": lambda: self.search_bar_find(), "on_next": lambda: app.tool_manager.get_tool("redact").navigate_next() if app.tool_manager.get_tool("redact") else None,
                "on_prev": lambda: app.tool_manager.get_tool("redact").navigate_prev() if app.tool_manager.get_tool("redact") else None,
                "on_redact_one": lambda: self.search_bar_redact_one(), "on_redact_all": lambda: self.search_bar_redact_all(), "on_close": lambda: self.toggle_search_bar(),
            },
        )

    def flash_status(self, message: str, color=None, duration_ms=3000) -> None: self.status_bar.flash(message, color=color, duration_ms=duration_ms)
    def set_top_bar_title(self, title: str) -> None: self.top_bar.set_title(title)
    def update_zoom_label(self, scale: float, dpi: float) -> None:
        pct = int(scale / dpi * 100)
        self.top_bar.set_zoom_label(f"{pct}%")
        self.status_bar.set_zoom(f"Zoom {pct}%")
    def update_view_mode_buttons(self, continuous: bool) -> None: self.top_bar.update_view_mode_buttons(continuous)
    def on_page_changed(self, idx: int, page_count: int, width: float, height: float) -> None:
        self.right_panel.update_page_label(idx + 1, page_count)
        self.status_bar.set_page_size(f"{int(width)} × {int(height)} pt")
        self.right_panel.thumb.refresh_all_borders()
        self.right_panel.thumb.scroll_to_active()
    def toggle_inspector(self) -> None:
        self.right_panel.toggle_visibility()
        self.top_bar.set_inspector_active(getattr(self.right_panel, "_visible", True))

    def set_single_mode(self) -> None:
        self.app.tool_manager.commit_all_boxes()
        self.app.viewport.set_view_mode(continuous=False)
        self.update_view_mode_buttons(False)

    def set_continuous_mode(self) -> None:
        self.app.tool_manager.commit_all_boxes()
        self.app.viewport.set_view_mode(continuous=True)
        self.update_view_mode_buttons(True)

    def toggle_search_bar(self) -> None:
        if self.canvas_area.search_bar_visible:
            self.canvas_area.hide_search_bar()
            self.search_bar_clear()
        else:
            self.canvas_area.show_search_bar()
            if self.app.tool_manager.active_tool_name != "redact": self.app.tool_manager.select_tool("redact")

    def search_bar_find(self) -> None:
        if not self.app.doc or not self.canvas_area.search_query: return
        if self.app.tool_manager.active_tool_name != "redact": self.app.tool_manager.select_tool("redact")
        rt = self.app.tool_manager.get_tool("redact")
        if rt and rt.search_all_pages(self.canvas_area.search_query, case_sensitive=self.canvas_area.search_case_sensitive) == 0:
            self.canvas_area.update_hit_display(-1, 0)
            self.flash_status(f'No matches for "{self.canvas_area.search_query}"', color=PALETTE["fg_secondary"])

    def search_bar_redact_one(self) -> None:
        if rt := self.app.tool_manager.get_tool("redact"): rt.redact_current_hit()
        self.right_panel.hide_redact_confirm()

    def search_bar_redact_all(self) -> None:
        if rt := self.app.tool_manager.get_tool("redact"): rt.redact_all_hits()
        self.right_panel.hide_redact_confirm()

    def search_bar_clear(self) -> None:
        if rt := self.app.tool_manager.get_tool("redact"):
            if rt.has_search_hits: rt.cancel_search()
        self.canvas_area.clear_hit_display()

    def _on_canvas_configure(self, event: tk.Event) -> None:
        if hasattr(self, "_config_after_id") and self._config_after_id: self.root.after_cancel(self._config_after_id)
        self._config_after_id = self.root.after(150, lambda: (self.app.viewport.render(), setattr(self, '_config_after_id', None)))

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        if self.app.viewport.continuous_mode:
            idx = self.app.viewport._cont_page_at_y(cy)
            if idx != self.app.viewport.current_page_idx: self.app._navigate_to(idx)
        return ((cx - self.app.viewport.page_offset_x) / self.app.viewport.scale_factor, (cy - self.app.viewport.page_offset_y) / self.app.viewport.scale_factor)

    def _on_mousewheel(self, event: tk.Event) -> None:
        if event.num == 4: self.canvas_area.canvas.yview_scroll(-1, "units")
        elif event.num == 5: self.canvas_area.canvas.yview_scroll(1, "units")
        else: self.canvas_area.canvas.yview_scroll(-1 * (event.delta // 120), "units")

    def _on_mouse_motion(self, event: tk.Event) -> None:
        if not self.app.doc: return
        cx, cy = self.canvas_area.canvas.canvasx(event.x), self.canvas_area.canvas.canvasy(event.y)
        self.status_bar.set_coords(*self._canvas_to_pdf(cx, cy))
        self.app.tool_manager.handle_motion(cx, cy)

    def show_startup_screen(self) -> None:
        if self.app.doc: return
        self.hide_startup_screen()
        frame = tk.Frame(self.canvas_area.canvas, bg=PALETTE["bg_dark"])
        self.startup_frame = frame
        inner = tk.Frame(frame, bg=PALETTE["bg_dark"])
        inner.place(relx=0.5, rely=0.5, anchor="center")
        
        tk.Label(inner, text="◼", bg=PALETTE["bg_dark"], fg=PALETTE["accent"], font=("Helvetica Neue", 52)).pack(pady=(0, 4))
        tk.Label(inner, text="PDF Editor", bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"], font=("Helvetica Neue", 22, "bold")).pack()
        tk.Label(inner, text="Open a PDF file to get started", bg=PALETTE["bg_dark"], fg=PALETTE["fg_dim"], font=("Helvetica Neue", 10)).pack(pady=(4, 20))
        tk.Button(inner, text="  Open PDF…  ", command=lambda: self.app.document_controller.open_pdf(), bg=PALETTE["accent"], fg=PALETTE["fg_inverse"], activebackground=PALETTE["accent_light"], activeforeground=PALETTE["fg_inverse"], font=("Helvetica Neue", 12, "bold"), relief="flat", bd=0, padx=28, pady=10, cursor="hand2", highlightthickness=0).pack(pady=(0, 28))

        recents = self.app.settings.get_recent_files()
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
                def _click(e, fp=p): self.app.document_controller.open_pdf_path(fp)

                for w in (row, nl, pl): w.bind("<Enter>", _enter); w.bind("<Leave>", _leave); w.bind("<Button-1>", _click)
            tk.Frame(inner, bg=PALETTE["border"], height=1).pack(fill=tk.X, pady=(4, 0))
        frame.place(x=0, y=0, relwidth=1, relheight=1)

    def hide_startup_screen(self) -> None:
        if self.startup_frame:
            try: self.startup_frame.destroy()
            except Exception: pass
            self.startup_frame = None

    def rebuild_recent_menu(self) -> None:
        menu_kw = dict(tearoff=0, bg=PALETTE["bg_panel"], fg=PALETTE["fg_primary"], activebackground=PALETTE["accent_dim"], activeforeground=PALETTE["accent_light"], font=("Helvetica Neue", 9), relief="flat", bd=1)
        menu = tk.Menu(self.root, **menu_kw)
        recents = self.app.settings.get_recent_files()
        if recents:
            for p in recents:
                label, dirname = os.path.basename(p), os.path.dirname(p)
                if len(dirname) > 40: dirname = "…" + dirname[-38:]
                menu.add_command(label=f"  {label}\n  {dirname}", command=lambda fp=p: self.app.document_controller.open_recent(fp))
            menu.add_separator()
            menu.add_command(label="  Clear recent files", command=self.clear_recent, foreground=PALETTE["fg_dim"])
        else: menu.add_command(label="  No recent files", state="disabled")
        self.top_bar.set_recent_menu(menu)

    def clear_recent(self) -> None:
        self.app.settings.clear_recent_files()
        self.rebuild_recent_menu()
        if self.startup_frame: self.show_startup_screen()