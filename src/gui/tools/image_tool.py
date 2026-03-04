"""
ImageTool — handles image insertion (drag-to-place) and extraction (click-on-image).

Two distinct sub-behaviours are unified here because they share the same
"insert_image" / "extract" tool slot in the sidebar.
"""

import os
import tkinter as tk
from tkinter import filedialog, messagebox

from src.gui.tools.base_tool import BaseTool
from src.gui.theme import PALETTE
from src.commands.insert_image import InsertImageCommand
from src.commands.extract_images import ExtractSingleImageCommand


class ImageInsertTool(BaseTool):
    """
    Two-step workflow:
      1. First click → open file picker to choose an image.
      2. Drag on canvas → rubber-band to define placement rect → release → insert.
    """

    MIN_DRAG_PX = 10

    def __init__(self, ctx, image_service, set_hint):
        super().__init__(ctx)
        self._service      = image_service
        self._set_hint     = set_hint
        self._pending_path: str | None = None
        self._drag_start:   tuple | None = None
        self._rubber_band:  int | None   = None

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self):
        self.ctx.canvas.config(cursor="crosshair")
        self._set_hint(
            "Click canvas to choose\nan image file, then drag\nto place it.",
        )

    def deactivate(self):
        self._cancel()

    # ── events ────────────────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float):
        if self._pending_path is None:
            self._pick_file()
        else:
            # File already chosen — start the drag
            self._drag_start  = (canvas_x, canvas_y)
            self._rubber_band = None

    def on_drag(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None:
            return
        x0, y0 = self._drag_start
        if self._rubber_band is None:
            self._rubber_band = self.ctx.canvas.create_rectangle(
                x0, y0, canvas_x, canvas_y,
                outline=PALETTE["accent_light"], width=2, dash=(5, 3),
            )
        else:
            self.ctx.canvas.coords(self._rubber_band, x0, y0, canvas_x, canvas_y)

    def on_release(self, canvas_x: float, canvas_y: float):
        if self._drag_start is None:
            return

        x0, y0       = self._drag_start
        pending_path = self._pending_path

        self._cancel_rubber_band()
        self._drag_start    = None
        self._pending_path  = None

        if abs(canvas_x - x0) < self.MIN_DRAG_PX or abs(canvas_y - y0) < self.MIN_DRAG_PX:
            return
        if not pending_path:
            return

        px0, py0 = self._canvas_to_pdf(min(x0, canvas_x), min(y0, canvas_y))
        px1, py1 = self._canvas_to_pdf(max(x0, canvas_x), max(y0, canvas_y))

        cmd = InsertImageCommand(
            self._service, self.ctx.doc,
            self.ctx.current_page,
            (px0, py0, px1, py1),
            pending_path,
        )
        try:
            cmd.execute()
            self.ctx.push_history(cmd)
        except Exception as ex:
            cmd.cleanup()
            messagebox.showerror("Insert Image Error", str(ex))
            return

        self.ctx.render()

    # ── internals ─────────────────────────────────────────────────────────────

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Choose Image to Insert — then drag to place it",
            filetypes=[
                ("Image Files", "*.png *.jpg *.jpeg *.bmp *.tiff *.tif *.gif"),
                ("All Files", "*.*"),
            ],
        )
        if not path:
            return
        self._pending_path = path
        self._set_hint(
            f"✓ {os.path.basename(path)}\n\nNow drag on the canvas\nto place the image.",
        )

    def _cancel_rubber_band(self):
        if self._rubber_band is not None:
            self.ctx.canvas.delete(self._rubber_band)
            self._rubber_band = None

    def _cancel(self):
        self._cancel_rubber_band()
        self._drag_start   = None
        self._pending_path = None
        self._set_hint(
            "Click canvas to choose\nan image file, then drag\nto place it.",
        )


class ImageExtractTool(BaseTool):
    """Click on an image region to extract and save it."""

    def __init__(self, ctx, image_service):
        super().__init__(ctx)
        self._service = image_service

    def activate(self):
        self.ctx.canvas.config(cursor="arrow")

    def on_click(self, canvas_x: float, canvas_y: float):
        pdf_x, pdf_y = self._canvas_to_pdf(canvas_x, canvas_y)
        page   = self.ctx.doc.get_page(self.ctx.current_page)
        images = page.get_image_info()
        for img in images:
            x0, y0, x1, y1 = img["bbox"]
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                xref = img["xref"]
                try:
                    data = self.ctx.doc.extract_image_by_xref(xref)
                    ext  = data.get("ext", "png")
                except Exception as ex:
                    messagebox.showerror("Error", str(ex))
                    return
                out = filedialog.asksaveasfilename(
                    title="Save Image",
                    defaultextension=f".{ext}",
                    initialfile=f"extracted.{ext}",
                )
                if out:
                    ExtractSingleImageCommand(
                        self._service, self.ctx.doc, xref, out).execute()
                    messagebox.showinfo("Extracted", f"Saved to:\n{out}")
                return
        messagebox.showinfo(
            "No Image",
            "No image found at that position.\nClick directly on an image.",
        )