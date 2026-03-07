# src/gui/controllers/ocr_controller.py
from __future__ import annotations
from tkinter import messagebox
from typing import Callable, Any

from src.commands.ocr_page import OcrPageCommand, generate_ocr_data

class OcrController:
    """Manages background text extraction and mutation commands for OCR operations."""
    def __init__(
        self, root: Any, get_doc: Callable, get_current_page: Callable, task_manager: Any,
        status_bar: Any, viewport: Any, push_history: Callable, mark_dirty: Callable, flash_status: Callable
    ) -> None:
        self.root = root
        self.get_doc = get_doc
        self.get_current_page = get_current_page
        self.task_manager = task_manager
        self.status_bar = status_bar
        self.viewport = viewport
        self.push_history = push_history
        self.mark_dirty = mark_dirty
        self.flash_status = flash_status

    def ocr_current_page(self) -> None:
        doc = self.get_doc()
        if not doc: return
        page_idx = self.get_current_page()
        self.status_bar.show_progress("Running Tesseract OCR...")

        def on_complete(ocr_words):
            if not ocr_words:
                self.status_bar.hide_progress("OCR — page already has text, skipped")
                return
            cmd = OcrPageCommand(doc, page_idx, ocr_words)
            cmd.execute()
            self.push_history(cmd)
            self.mark_dirty()
            self.viewport.render()
            self.status_bar.hide_progress("OCR Complete")

        def on_error(err: Exception):
            messagebox.showerror("OCR Error", str(err))
            self.status_bar.hide_progress("OCR Failed")

        self.task_manager.run_task(worker_func=lambda: generate_ocr_data(doc, page_idx), on_complete=on_complete, on_error=on_error)

    def ocr_all_pages(self) -> None:
        doc = self.get_doc()
        if not doc:
            messagebox.showinfo("OCR", "Please open a PDF document first.")
            return
        page_count = doc.page_count
        if not messagebox.askyesno("OCR All Pages", f"Run OCR on all {page_count} pages? This may take a while for large documents."): return

        self.status_bar.show_progress(f"Running OCR on all {page_count} pages...")
        self.root.config(cursor="watch")

        def worker():
            results = []
            for idx in range(page_count): results.append((idx, generate_ocr_data(doc, idx)))
            return results

        def on_complete(results: list[tuple[int, bytes]]):
            self.root.config(cursor="")
            errors = []
            skipped = 0
            for idx, ocr_words in results:
                if not ocr_words:
                    skipped += 1
                    continue
                cmd = OcrPageCommand(doc, idx, ocr_words)
                try:
                    cmd.execute()
                    self.push_history(cmd)
                except Exception as ex:
                    cmd.cleanup()
                    errors.append(f"Page {idx + 1}: {ex}")
            
            self.mark_dirty()
            self.viewport.invalidate_cache()
            self.viewport.render()
            self.status_bar.hide_progress("Batch OCR Complete")

            if errors:
                messagebox.showwarning("OCR Complete (with errors)", f"OCR finished with {len(errors)} error(s):\n" + "\n".join(errors[:5]))
            else:
                self.flash_status(f"✓ OCR complete on all {page_count} pages — text is now selectable.")

        def on_error(err: Exception):
            self.root.config(cursor="")
            messagebox.showerror("Batch OCR Error", str(err))
            self.status_bar.hide_progress("OCR Failed")

        self.task_manager.run_task(worker_func=worker, on_complete=on_complete, on_error=on_error)