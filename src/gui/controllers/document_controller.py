# src/gui/controllers/document_controller.py
from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox
from typing import Callable, Any

from src.core.document import PDFDocument
from src.commands.convert_images import ConvertImagesToPdfCommand
from src.gui.theme import PALETTE

try:
    from src.gui.panels.merge_split_dialog import MergeSplitDialog
    _HAS_MERGE_SPLIT = True
except ImportError:
    _HAS_MERGE_SPLIT = False

class DocumentController:
    def __init__(self, root: tk.Tk, image_conversion_service: Any, merge_split_service: Any, history: Any, settings: Any, viewport: Any, tool_manager: Any, ui: dict[str, Callable]) -> None:
        self.root = root
        self.image_conversion_service = image_conversion_service
        self.merge_split_service = merge_split_service
        self.history = history
        self.settings = settings
        self.viewport = viewport
        self.tool_manager = tool_manager
        self.ui = ui

        self.doc: PDFDocument | None = None
        self.current_path: str | None = None
        self.unsaved_changes: bool = False
        self.is_staging_mode: bool = False
        self.staging_images: list[str] = []
        self.staging_ocr_var = tk.BooleanVar(value=False)

    def mark_dirty(self) -> None:
        if not self.unsaved_changes:
            self.unsaved_changes = True
            self.update_title()

    def update_title(self) -> None:
        if self.current_path:
            name, marker = os.path.basename(self.current_path), " •" if self.unsaved_changes else ""
            title = f"{name}{marker}"
        else: title = "PDF Editor" + (" — Untitled •" if self.unsaved_changes else "")
        self.root.title(f"PDF Editor — {title}" if self.current_path else title)
        self.ui["set_top_bar_title"](os.path.basename(self.current_path) + (" •" if self.unsaved_changes else "") if self.current_path else "PDF Editor")

    def open_pdf(self) -> None:
        if self.unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes.\nSave before opening?")
            if ans is None: return
            if ans and not self.save_pdf(): return
        path = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf"), ("All", "*.*")])
        if path: self.open_pdf_path(path)

    def open_pdf_path(self, path: str) -> None:
        self.is_staging_mode = False
        self.tool_manager.commit_all_boxes()
        if self.doc: self.doc.close()
        try: self.doc = PDFDocument(path)
        except Exception as ex: return messagebox.showerror("Error", f"Could not open:\n{ex}")
        self.viewport.current_page_idx = 0
        self.current_path = path
        self.unsaved_changes = False
        self.history.clear()
        self.viewport.invalidate_cache()
        self.settings.add_recent_file(path)
        self.ui["rebuild_recent_menu"]()
        self.ui["hide_startup_screen"]()
        self.update_title()
        self.viewport.render()
        self.ui["thumb_reset"]()
        self.ui["refresh_toc"]()
        self.root.after(80, self.viewport.zoom_fit_width)

    def open_recent(self, path: str) -> None:
        if self.unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "You have unsaved changes.\nSave before opening?")
            if ans is None: return
            if ans and not self.save_pdf(): return
        self.open_pdf_path(path)

    def save_pdf(self) -> bool:
        if self.is_staging_mode: return self.generate_pdf_from_staging()
        if not self.doc: return False
        if not self.current_path: return self.save_pdf_as()
        self.tool_manager.commit_all_boxes()
        try:
            self.doc.save(self.current_path, incremental=True)
            self.unsaved_changes = False
            self.history.mark_saved()
            self.update_title()
            self.ui["flash_status"]("✓ Saved")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    def save_pdf_as(self) -> bool:
        if not self.doc: return False
        self.tool_manager.commit_all_boxes()
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], initialfile=os.path.basename(self.current_path) if self.current_path else "document.pdf")
        if not path: return False
        try:
            self.doc.save(path)
            self.current_path = path
            self.unsaved_changes = False
            self.doc.path = path
            self.history.mark_saved()
            self.update_title()
            self.ui["flash_status"](f"✓ Saved as {os.path.basename(path)}")
            return True
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))
            return False

    def get_image_thumbnail(self, path: str, width: int) -> bytes: return self.image_conversion_service.get_image_thumbnail(path, width)

    def start_image_staging(self) -> None:
        if self.unsaved_changes:
            ans = messagebox.askyesnocancel("Unsaved Changes", "Save before continuing?")
            if ans is None: return
            if ans and not self.save_pdf(): return
        paths = filedialog.askopenfilenames(title="Select Images to Combine into PDF", filetypes=[("Image Files", "*.jpg *.jpeg *.png *.bmp *.tiff")])
        if not paths: return
        self.tool_manager.commit_all_boxes()
        if self.doc:
            self.doc.close()
            self.doc = None
        self.staging_images = list(paths)
        self.is_staging_mode = True
        self.current_path = None
        self.update_title()
        self.ui["thumb_reset_for_images"](self.staging_images)
        self.ui["flash_status"]("Staging: drag thumbnails to reorder, then Save.")
        self.preview_staging_image(0)

    def preview_staging_image(self, idx: int) -> None:
        if not self.is_staging_mode or idx >= len(self.staging_images): return
        self.viewport.current_page_idx = idx
        path = self.staging_images[idx]
        canvas_w = self.viewport.canvas.winfo_width()
        preview_w = int(canvas_w * 0.8 * self.viewport.scale_factor)
        img_bytes = self.get_image_thumbnail(path, width=preview_w)
        if img_bytes:
            self.viewport.tk_image = tk.PhotoImage(data=img_bytes)
            self.viewport.canvas.delete("all")
            self.viewport.canvas.create_image(canvas_w // 2, 40, anchor=tk.N, image=self.viewport.tk_image, tags="page_img")
            self.ui["update_page_label"](idx + 1, len(self.staging_images))
            self.ui["set_page_size"]("Image Preview")
            cb = tk.Checkbutton(self.viewport.canvas, text="Run OCR (make text selectable)", variable=self.staging_ocr_var, bg=PALETTE["bg_dark"], fg=PALETTE["fg_primary"], selectcolor=PALETTE["accent_dim"], activebackground=PALETTE["bg_hover"], highlightthickness=0)
            self.viewport.canvas.create_window(canvas_w // 2, 15, window=cb, tags="page_img")
            self.ui["thumb_refresh_all_borders"]()
            self.ui["thumb_scroll_to_active"]()

    def exit_staging_mode(self) -> None:
        if not self.is_staging_mode: return
        self.is_staging_mode = False
        self.staging_images.clear()
        self.viewport.canvas.delete("all")
        self.ui["thumb_reset"]()
        self.ui["show_startup_screen"]()
        self.ui["flash_status"]("Cancelled", color=PALETTE["fg_secondary"])

    def generate_pdf_from_staging(self) -> bool:
        if not self.staging_images: return False
        out_path = filedialog.asksaveasfilename(title="Save Generated PDF", defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")], initialfile="Combined_Images.pdf")
        if not out_path: return False
        self.root.config(cursor="watch")
        self.root.update()
        cmd = ConvertImagesToPdfCommand(self.image_conversion_service, self.staging_images, out_path, apply_ocr=self.staging_ocr_var.get())
        try:
            cmd.execute()
            if cmd.success:
                self.ui["flash_status"]("✓ PDF created")
                self.is_staging_mode = False
                self.staging_images.clear()
                self.staging_ocr_var.set(False)
                self.open_pdf_path(out_path)
                return True
            messagebox.showerror("Error", "Failed to create PDF from images.")
            return False
        finally:
            self.root.config(cursor="")

    def open_merge_split_dialog(self) -> None:
        if _HAS_MERGE_SPLIT: MergeSplitDialog(root=self.root, service=self.merge_split_service, current_doc=self.doc, on_open_path=self.open_pdf_path)