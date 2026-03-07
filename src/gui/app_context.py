# src/gui/app_context.py
import tkinter as tk
from src.core.document import PDFDocument

class AppContext:
    """
    Lightweight namespace passed to tool classes so they can reach shared
    application state without holding a reference to the full editor class.
    """

    def __init__(self, editor: "InteractivePDFEditor"):
        self._editor = editor
        self.on_tool_state_change = None

    # ── document / view state (read-only for tools) ───────────────────────────

    @property
    def canvas(self) -> tk.Canvas:
        return self._editor.canvas

    @property
    def doc(self) -> PDFDocument | None:
        return self._editor.doc

    @property
    def current_page(self) -> int:
        return self._editor.current_page_idx

    @property
    def scale(self) -> float:
        if hasattr(self._editor, "viewport"):
            return self._editor.viewport.scale_factor
        return 1.0

    @property
    def page_offset_x(self) -> float:
        if hasattr(self._editor, "viewport"):
            return self._editor.viewport.page_offset_x
        return 0.0

    @property
    def page_offset_y(self) -> float:
        if hasattr(self._editor, "viewport"):
            return self._editor.viewport.page_offset_y
        return 0.0

    # ── actions (tools call these to drive the window) ────────────────────────

    def invalidate_cache(self, page_idx: int = None) -> None:
        if hasattr(self._editor, "viewport"):
            self._editor.viewport.invalidate_cache(page_idx)

    def canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        if hasattr(self._editor, "ui"):
            return self._editor.ui._canvas_to_pdf(cx, cy)
        return (cx, cy)

    def push_history(self, cmd):
        self._editor._push_history(cmd)

    def render(self):
        if hasattr(self._editor, "viewport"):
            self._editor.viewport.render()

    def flash_status(self, message: str, color: str = None, duration_ms: int = 3000):
        if hasattr(self._editor, "ui"):
            self._editor.ui.flash_status(message, color, duration_ms)

    def navigate_to_page(self, idx: int) -> None:
        self._editor._navigate_to(idx)

    # ── tool-state protocol ───────────────────────────────────────────────────

    def set_tool_state(self, key: str, value: object) -> None:
        if self.on_tool_state_change is not None:
            self.on_tool_state_change(key, value)