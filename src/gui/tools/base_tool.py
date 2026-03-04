"""
BaseTool — abstract interface for all canvas interaction tools.

Each tool receives a reference to a shared AppContext (a lightweight
namespace that holds the document, canvas, services, and callbacks) so
individual tools can dispatch commands and update UI without coupling
to the full InteractivePDFEditor class.
"""

from abc import ABC, abstractmethod


class BaseTool(ABC):
    """
    Abstract base class for canvas interaction tools.

    Subclasses implement the event-handler methods they care about; the
    default implementations are no-ops so subclasses only override what
    they need.

    Each tool is given a *context* object at construction that exposes:
        ctx.canvas          — tk.Canvas
        ctx.doc             — PDFDocument | None
        ctx.current_page    — int (property)
        ctx.scale           — float (property)
        ctx.page_offset_x   — float (property)
        ctx.page_offset_y   — float (property)
        ctx.push_history()  — records a command and marks the doc dirty
        ctx.render()        — re-render the current page
        ctx.flash_status()  — show a transient status-bar message
        ctx.canvas_to_pdf() — convert canvas → PDF coords
    """

    def __init__(self, ctx):
        self.ctx = ctx

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def activate(self) -> None:
        """Called when this tool becomes the active tool."""

    def deactivate(self) -> None:
        """Called when switching away from this tool; should cancel any in-progress operations."""

    # ── canvas events ─────────────────────────────────────────────────────────

    def on_click(self, canvas_x: float, canvas_y: float) -> None:
        """Mouse button-1 pressed."""

    def on_drag(self, canvas_x: float, canvas_y: float) -> None:
        """Mouse button-1 held and moved."""

    def on_release(self, canvas_x: float, canvas_y: float) -> None:
        """Mouse button-1 released."""

    def on_motion(self, canvas_x: float, canvas_y: float) -> None:
        """Mouse moved (no button held) — used for hover effects."""

    # ── helpers ───────────────────────────────────────────────────────────────

    def _canvas_to_pdf(self, cx: float, cy: float) -> tuple[float, float]:
        return self.ctx.canvas_to_pdf(cx, cy)