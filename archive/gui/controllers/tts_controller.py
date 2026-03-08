# src/gui/controllers/tts_controller.py
from __future__ import annotations
import tkinter as tk
from tkinter import messagebox
from typing import Callable

from src.services.tts_service import TtsService
from src.gui.widgets.tts_bar import TtsBar
from src.gui.theme import PALETTE

class TtsController:
    """Manages the lifecycle, UI state, and playback of Text-to-Speech features."""
    def __init__(
        self, root: tk.Tk, get_doc: Callable, get_current_page: Callable,
        canvas_area: Any, get_selection_text: Callable, viewport: Any, flash_status: Callable
    ) -> None:
        self.root = root
        self.get_doc = get_doc
        self.get_current_page = get_current_page
        self.canvas_area = canvas_area
        self.get_selection_text = get_selection_text
        self.viewport = viewport
        self.flash_status = flash_status

        self.service = TtsService(
            on_start=self._on_start, on_playback_start=self._on_playback_start,
            on_progress=self._on_progress, on_stop=self._on_stop, on_error=self._on_error
        )
        self.tts_bar = TtsBar(
            root, on_stop=self.stop, on_pause_resume=self.pause_resume, on_speed_change=self.set_speed
        )
        self.canvas_area.mount_tts_bar(self.tts_bar._bar)

    def _extract_page_text(self, page_idx: int) -> str:
        doc = self.get_doc()
        if not doc: return ""
        return doc._doc[page_idx].get_text("text").strip()

    def read_page(self) -> None:
        doc = self.get_doc()
        if not doc:
            messagebox.showinfo("Read Aloud", "Please open a PDF document first.")
            return
        idx = self.get_current_page()
        text = self._extract_page_text(idx)
        if not text:
            messagebox.showinfo("Read Aloud", "No readable text found on this page.\nTry running OCR first.")
            return
        label = f"Reading page {idx + 1}…"
        self.canvas_area.show_tts_bar(label)
        self.tts_bar.set_status(label)
        self.service.speak(text)

    def read_all(self) -> None:
        doc = self.get_doc()
        if not doc:
            messagebox.showinfo("Read Aloud", "Please open a PDF document first.")
            return
        pages = [t for i in range(doc.page_count) if (t := self._extract_page_text(i))]
        if not pages:
            messagebox.showinfo("Read Aloud", "No readable text found.\nTry running OCR first.")
            return
        label = f"Reading all {doc.page_count} pages…"
        self.canvas_area.show_tts_bar(label)
        self.tts_bar.set_status(label)
        self.service.speak("\n\n".join(pages))

    def read_selection(self) -> None:
        if not self.get_doc():
            messagebox.showinfo("Read Aloud", "Please open a PDF document first.")
            return
        text = self.get_selection_text()
        if not text.strip():
            messagebox.showinfo("Read Aloud", "No text selected.\nSwitch to the Select Text tool (S) and drag to highlight text first.")
            return
        self.canvas_area.show_tts_bar("Reading selection…")
        self.tts_bar.set_status("Reading selection…")
        self.service.speak(text.strip())

    def stop(self) -> None:
        self.service.stop()
        self.canvas_area.hide_tts_bar()

    def pause_resume(self) -> None:
        self.service.toggle_pause()
        self.tts_bar.set_paused(self.service.is_paused)

    def set_speed(self, speed: float) -> None:
        self.service.speed = speed

    def _on_start(self) -> None:
        self.root.after(0, lambda: (
            self.tts_bar.show_loading(),
            self.root.after(50, lambda: self.viewport.schedule_cont_render(self.get_current_page()) if self.viewport.continuous_mode and self.get_doc() else self.viewport.render())
        ))

    def _on_progress(self, done: int, total: int, pct: int) -> None:
        self.root.after(0, lambda d=done, t=total, p=pct: self.tts_bar.update_progress(d, t, p))

    def _on_playback_start(self) -> None:
        self.root.after(0, lambda: [self.tts_bar.show_playback_controls(), self.tts_bar.set_paused(False)])

    def _on_stop(self) -> None:
        self.root.after(0, self.canvas_area.hide_tts_bar)

    def _on_error(self, msg: str) -> None:
        self.root.after(0, lambda: (
            self.flash_status("TTS error: " + msg, color=PALETTE["danger"], duration_ms=6000),
            self.canvas_area.hide_tts_bar()
        ))

    def shutdown(self) -> None:
        try: self.service.stop()
        except Exception: pass