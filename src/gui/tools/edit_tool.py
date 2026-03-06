import tkinter as tk
from src.gui.tools.base_tool import BaseTool
from src.gui.widgets.edit_overlay import EditOverlay
from src.commands.edit_text_command import EditTextCommand

class EditTextTool(BaseTool):
    """
    Tool that hit-tests paragraph blocks, extracts properties, and spawns the 
    Tkinter editing overlay.
    """
    def __init__(self, ctx, text_service, redaction_service):
        super().__init__(ctx)
        self.text_service = text_service
        self.redaction_service = redaction_service
        self.current_overlay = None

    def activate(self):
        self.ctx.canvas.config(cursor="ibeam")

    def deactivate(self):
        if self.current_overlay:
            self.current_overlay.destroy_overlay()
            self.current_overlay = None

    def on_click(self, canvas_x: float, canvas_y: float):
        # Force commit if clicking elsewhere on the canvas
        if self.current_overlay:
            self.ctx.canvas.focus_set()
            return

        p, ox, oy = self._resolve_page_and_offsets(canvas_y)
        if not self.ctx.doc:
            return
            
        page = self.ctx.doc.get_page(p)
        page_dict = page.get_text_dict()
        
        s = self.ctx.scale
        pdf_x = (canvas_x - ox) / s
        pdf_y = (canvas_y - oy) / s

        # Find which paragraph block was clicked
        clicked_block = None
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0: 
                continue
            x0, y0, x1, y1 = block.get("bbox", [0,0,0,0])
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                clicked_block = block
                break
                
        if not clicked_block:
            return

        # Extract styling from the first character span
        first_span = None
        for line in clicked_block.get("lines", []):
            spans = line.get("spans", [])
            if spans:
                first_span = spans[0]
                break

        if not first_span:
            return

        # Reconstruct natural paragraph text
        full_text = ""
        for line in clicked_block.get("lines", []):
            for span in line.get("spans", []):
                full_text += span.get("text", "")
            full_text += "\n"
        full_text = full_text.strip()

        # Parse font details
        font_name = first_span.get("font", "helv")
        if "+" in font_name: # Strip subset tags (e.g. ABCDEF+Arial)
            font_name = font_name.split("+")[1]
            
        font_size = first_span.get("size", 12)
        
        # Convert PDF integer sRGB to Tkinter Hex and RGB Tuple
        srgb = first_span.get("color", 0)
        r = (srgb >> 16) & 0xFF
        g = (srgb >> 8) & 0xFF
        b = srgb & 0xFF
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        color_rgb = (r/255.0, g/255.0, b/255.0)

        # --- Calculate exact line spacing (leading) ---
        lines = clicked_block.get("lines", [])
        line_spacing = 1.2 # PyMuPDF default fallback
        
        if len(lines) > 1:
            # Measure distance between the top of line 1 and top of line 2
            y_diff = lines[1]["bbox"][1] - lines[0]["bbox"][1]
            line_spacing = y_diff / font_size
        elif len(lines) == 1:
            # Estimate from the single line's height
            h = lines[0]["bbox"][3] - lines[0]["bbox"][1]
            line_spacing = h / font_size
            
        # Clamp it to a sane range to prevent crazy values from OCR anomalies
        line_spacing = max(0.8, min(2.5, line_spacing))

        def on_commit(new_text, pdf_bbox):
            self.current_overlay = None
            if new_text == full_text:
                return
                
            cmd = EditTextCommand(
                self.redaction_service,
                self.text_service,
                self.ctx.doc,
                p,
                pdf_bbox,
                new_text,
                full_text,
                font_name,
                font_size,
                color_rgb,
                line_spacing  # Pass the calculated spacing to the command
            )
            try:
                cmd.execute()
                self.ctx.push_history(cmd)
                if hasattr(self.ctx, "invalidate_cache"):
                    self.ctx.invalidate_cache(p)
                self.ctx.render()
                self.ctx.flash_status("✓ Text updated")
            except Exception as ex:
                cmd.cleanup()
                print(f"Edit failed: {ex}")

        # Spawn the overlay widget
        self.current_overlay = EditOverlay(
            self.ctx.canvas,
            clicked_block["bbox"],
            full_text,
            font_name,
            font_size,
            color_hex,
            s,
            ox, 
            oy,
            on_commit
        )

    def _resolve_page_and_offsets(self, cy: float) -> tuple[int, float, float]:
        editor = self.ctx._editor
        if getattr(editor, "_continuous_mode", False) and self.ctx.doc:
            page_idx = editor._cont_page_at_y(cy)
            oy = editor._cont_page_top(page_idx)
            try:
                p = self.ctx.doc.get_page(page_idx)
                iw = int(p.width * self.ctx.scale)
                cw = self.ctx.canvas.winfo_width()
                ox = max(50, (cw - iw) // 2)
            except Exception:
                ox = self.ctx.page_offset_x
            return page_idx, ox, oy
        return self.ctx.current_page, self.ctx.page_offset_x, self.ctx.page_offset_y