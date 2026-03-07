# src/gui/tools/tool_manager.py
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import Callable, Any

from src.gui.app_context import AppContext
from src.gui.theme import PALETTE
from src.gui.widgets.text_box import TextBox
from src.commands.insert_text import InsertTextBoxCommand
from src.commands.draw_command import DrawAnnotationCommand

from src.gui.tools.annot_tool  import AnnotationTool
from src.gui.tools.image_tool  import ImageInsertTool, ImageExtractTool
from src.gui.tools.select_tool import SelectTextTool
from src.gui.tools.redact_tool import RedactTool
from src.gui.tools.draw_tool   import DrawTool
from src.gui.tools.edit_tool   import EditTextTool


class ToolManager:
    """
    Centralizes tool initialization, state switching, and style management.
    Handles the lifecycle of text boxes and routes canvas events to the active tool.
    """
    def __init__(
        self,
        ctx: AppContext,
        services: dict[str, Any],
        ui_callbacks: dict[str, Callable]
    ) -> None:
        self.ctx = ctx
        self.services = services
        self.ui = ui_callbacks
        
        # Tool Style State
        self.style: dict = {
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

        # Active State
        self.tools: dict = {}
        self.active_tool_name: str = "text"
        self.current_tool = None
        
        # Text Box Lifecycle
        self.text_boxes: list[TextBox] = []
        self.suppress_next_click = False

        self._init_tools()

    def _init_tools(self) -> None:
        s = self.style
        srv = self.services
        self.tools["highlight"] = AnnotationTool(
            self.ctx, srv["annotation"], "highlight",
            get_stroke_rgb=lambda: s["annot_stroke_rgb"], get_fill_rgb=lambda: s["annot_fill_rgb"], get_width=lambda: s["annot_width"]
        )
        self.tools["rect_annot"] = AnnotationTool(
            self.ctx, srv["annotation"], "rect_annot",
            get_stroke_rgb=lambda: s["annot_stroke_rgb"], get_fill_rgb=lambda: s["annot_fill_rgb"], get_width=lambda: s["annot_width"]
        )
        self.tools["insert_image"] = ImageInsertTool(self.ctx, srv["image"], set_hint=lambda t: None)
        self.tools["extract"]      = ImageExtractTool(self.ctx, srv["image"])
        self.tools["select_text"]  = SelectTextTool(self.ctx, self.ui["root"])
        self.tools["edit_text"]    = EditTextTool(self.ctx, srv["text"], srv["redaction"])
        self.tools["redact"]       = RedactTool(
            self.ctx, srv["redaction"],
            get_fill_color=lambda: s["redact_fill_color"], get_replacement_text=lambda: s["redact_label"],
            on_navigate_page=self.ui["navigate_to"], on_hit_changed=self._on_search_hit_changed
        )
        self.tools["draw"]         = DrawTool(
            self.ctx, annotation_service=srv["annotation"],
            get_mode=lambda: s["draw_mode"], get_stroke_rgb=lambda: s["draw_stroke_rgb"],
            get_fill_rgb=lambda: s["draw_fill_rgb"], get_width=lambda: s["draw_width"],
            get_opacity=lambda: s["draw_opacity"], on_committed=self._on_draw_committed
        )

    def get_tool(self, name: str):
        return self.tools.get(name)

    def select_tool(self, name: str) -> None:
        self.active_tool_name = name
        self.ui["set_status_tool"](name)

        if self.current_tool:
            self.current_tool.deactivate()

        if name != "redact":
            rt = self.get_tool("redact")
            if rt and rt.has_pending_hits:
                rt.cancel_hits()

        cursor_map = {
            "text": "crosshair", "insert_image": "crosshair", "highlight": "crosshair", "rect_annot": "crosshair",
            "select_text": "ibeam", "extract": "arrow", "redact": "crosshair", "draw": "crosshair", "edit_text": "ibeam",
        }
        self.ui["set_cursor"](cursor_map.get(name, "crosshair"))
        self.ui["set_icon_active"](name)
        self.ui["render_props"](name)
        self.ui["select_props_tab"]()

        self.current_tool = self.get_tool(name)
        if self.current_tool:
            self.current_tool.activate()

    # ── Tool / Style Routing ──────────────────────────────────────────────────

    def on_tool_style_change(self, key: str, value) -> None:
        if key == "redact.find":
            self._redact_find_from_props(value)
        elif key == "redact.confirm":
            self._redact_confirm()
        elif key == "redact.cancel":
            self._redact_cancel_hits()

        if key in ("font_index", "fontsize", "text_color", "text_align"):
            if self.text_boxes and self.active_tool_name == "text":
                self.text_boxes[-1].update_style(
                    font_index=self.style["font_index"], fontsize=self.style["fontsize"],
                    color_rgb=self.style["text_color"], align=self.style["text_align"],
                )

    def on_tool_state_change(self, key: str, value) -> None:
        pass

    # ── Canvas Inputs ─────────────────────────────────────────────────────────

    def handle_click(self, cx: float, cy: float) -> None:
        if self.suppress_next_click:
            self.suppress_next_click = False
            return
        if self.active_tool_name == "text":
            pdf_x, pdf_y = self.ctx.canvas_to_pdf(cx, cy)
            self._spawn_textbox(pdf_x, pdf_y)
        elif self.current_tool:
            self.current_tool.on_click(cx, cy)

    def handle_drag(self, cx: float, cy: float) -> None:
        if self.current_tool:
            self.current_tool.on_drag(cx, cy)

    def handle_release(self, cx: float, cy: float) -> None:
        if self.current_tool:
            self.current_tool.on_release(cx, cy)

    def handle_motion(self, cx: float, cy: float) -> None:
        if self.active_tool_name == "select_text" and self.current_tool:
            self.current_tool.on_motion(cx, cy)

    # ── Text Box Lifecycle ────────────────────────────────────────────────────

    def _spawn_textbox(self, pdf_x: float, pdf_y: float) -> None:
        if not self.ctx.doc: return
        page = self.ctx.doc.get_page(self.ctx.current_page)
        pdf_w = page.width * 0.42
        pdf_h = self.style["fontsize"] * 4
        bg = self._sample_page_color(pdf_x, pdf_y)
        
        box = TextBox(
            canvas=self.ctx.canvas, pdf_x=pdf_x, pdf_y=pdf_y, pdf_w=pdf_w, pdf_h=pdf_h,
            scale=self.ctx.scale, page_offset_x=self.ctx.page_offset_x, page_offset_y=self.ctx.page_offset_y,
            font_index=self.style["font_index"], fontsize=self.style["fontsize"],
            color_rgb=self.style["text_color"], entry_bg=bg, align=self.style["text_align"],
            on_commit=self._on_box_confirmed, on_delete=self._on_box_deleted, on_interact=self._on_box_interact,
        )
        self.text_boxes.append(box)

    def _sample_page_color(self, pdf_x: float, pdf_y: float) -> str:
        viewport = getattr(self.ctx._editor, "viewport", None)
        if not viewport: return "#FFFFFF"
        img = viewport._cont_images.get((self.ctx.current_page, self.ctx.scale)) if viewport.continuous_mode else viewport.tk_image
        if not img: return "#FFFFFF"
        try:
            return f"#{img.get(int(pdf_x * self.ctx.scale), int(pdf_y * self.ctx.scale))[0]:02x}{img.get(int(pdf_x * self.ctx.scale), int(pdf_y * self.ctx.scale))[1]:02x}{img.get(int(pdf_x * self.ctx.scale), int(pdf_y * self.ctx.scale))[2]:02x}"
        except Exception: return "#FFFFFF"

    def _on_box_confirmed(self, box: TextBox) -> None:
        self.text_boxes = [b for b in self.text_boxes if b is not box]
        text = box.get_text()
        if not text: return
        rect = (box.pdf_x, box.pdf_y, box.pdf_x + box.pdf_w + 5, box.pdf_y + box.pdf_h + 10)
        cmd = InsertTextBoxCommand(self.services["text"], self.ctx.doc, self.ctx.current_page, rect, text, box.fontsize, box.pdf_font_name, box.pdf_color, box.align)
        try:
            cmd.execute()
            self.ctx.push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Insert Error", str(ex))
            return
        self.ctx.render()

    def _on_box_interact(self) -> None:
        self.suppress_next_click = True

    def _on_box_deleted(self, box: TextBox) -> None:
        self.text_boxes = [b for b in self.text_boxes if b is not box]

    def commit_all_boxes(self) -> None:
        for box in list(self.text_boxes): box._confirm()
        self.text_boxes.clear()

    def dismiss_boxes(self) -> None:
        for box in list(self.text_boxes): box._delete()
        self.text_boxes.clear()

    def rescale_boxes(self) -> None:
        for box in list(self.text_boxes):
            box.rescale(self.ctx.scale, self.ctx.page_offset_x, self.ctx.page_offset_y)

    def copy_selected_text(self) -> None:
        t = self.get_tool("select_text")
        if t: t.copy()

    # ── Feature Handlers (Redact & Draw) ──────────────────────────────────────

    def _on_search_hit_changed(self, cur_idx: int, total: int) -> None:
        if total == 0 or cur_idx < 0:
            self.ui["update_hit_display"](-1, 0)
            return
        rt = self.get_tool("redact")
        self.ui["update_hit_display"](cur_idx, total, f"p.{rt._all_hits[cur_idx][0]+1}" if rt else "")
        self.ui["show_redact_confirm"](total)

    def _redact_find_from_props(self, params: dict) -> None:
        rt = self.get_tool("redact")
        if not rt or not self.ctx.doc: return
        query = params.get("query", "")
        if not query:
            self.ctx.flash_status("Enter a search term first", color=PALETTE["fg_secondary"])
            return
        if rt.search_all_pages(query, case_sensitive=params.get("case_sensitive", False)) == 0:
            self.ui["hide_redact_confirm"]()
            self.ctx.flash_status(f'No matches for "{query}"', color=PALETTE["fg_secondary"])

    def _redact_confirm(self) -> None:
        rt = self.get_tool("redact")
        if rt: rt.redact_all_hits()
        self.ui["hide_redact_confirm"]()
        self.ui["clear_hit_display"]()

    def _redact_cancel_hits(self) -> None:
        rt = self.get_tool("redact")
        if rt: rt.cancel_search()
        self.ui["hide_redact_confirm"]()
        self.ui["clear_hit_display"]()
        self.ctx.flash_status("Redaction cancelled", color=PALETTE["fg_secondary"])

    def _on_draw_committed(self, page_idx: int, xref: int) -> None:
        cmd = DrawAnnotationCommand(self.ctx.doc, page_idx, xref)
        self.ctx.push_history(cmd)
        self.ui["mark_dirty"]()
        self.ctx.invalidate_cache(page_idx)
        self.ui["mark_thumb_dirty"](page_idx)
        
        viewport = getattr(self.ctx._editor, "viewport", None)
        if viewport:
            if page_idx == self.ctx.current_page: viewport.render()
            elif viewport.continuous_mode: viewport._render_cont_page_refresh(page_idx)