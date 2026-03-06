import tkinter as tk

class EditOverlay(tk.Text):
    """
    A borderless, transparent-appearing text widget that overlays the PDF canvas
    to capture user input seamlessly.
    """
    def __init__(self, canvas, pdf_bbox, text, font_family, font_size, color_hex, scale_factor, ox, oy, on_commit):
        
        # FIX: Use a negative number to force absolute pixel sizing, ignoring OS DPI
        pixel_size = -max(8, int(font_size * scale_factor))
        
        super().__init__(
            canvas,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=(font_family, pixel_size),
            fg=color_hex,
            bg="#ffffff",
            wrap="word",
            undo=True
        )
        self.canvas = canvas
        self.pdf_bbox = pdf_bbox
        self.on_commit_callback = on_commit
        
        self.insert("1.0", text)
        
        self.bind("<FocusOut>", self._commit)
        self.bind("<Escape>", self._cancel)
        
        x0, y0, x1, y1 = pdf_bbox
        width = (x1 - x0) * scale_factor
        height = (y1 - y0) * scale_factor
        
        # FIX: Shift slightly to counter Tkinter's internal font ascender gap
        x_pos = (x0 * scale_factor) + ox - 1
        y_pos = (y0 * scale_factor) + oy - 1
        
        self.window_id = self.canvas.create_window(
            x_pos, 
            y_pos, 
            window=self, 
            anchor="nw", 
            width=width + 6, # Buffer to prevent premature Tkinter word wrapping
            height=max(25, height + 10) 
        )
        
        self.focus_set()

    def _commit(self, event=None):
        new_text = self.get("1.0", "end-1c").strip()
        self.on_commit_callback(new_text, self.pdf_bbox)
        self.destroy_overlay()
        
    def _cancel(self, event=None):
        self.destroy_overlay()
        
    def destroy_overlay(self):
        try:
            self.canvas.delete(self.window_id)
            self.destroy()
        except Exception:
            pass