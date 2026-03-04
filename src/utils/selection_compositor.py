"""
selection_compositor.py

Composites a text-selection highlight onto a rendered PDF page image using
real alpha blending.  Produces a tk.PhotoImage ready to display on a Canvas.

The function is intentionally standalone — it has no dependencies on any
GUI or tool class so it can be unit-tested independently.

Usage
-----
    from src.gui.utils.selection_compositor import composite_selection

    tk_image = composite_selection(
        ppm_bytes   = page.render_to_ppm(scale=scale),
        rects       = [(x0, y0, x1, y1), ...],   # PDF-space points
        scale       = scale_factor,
        color       = (74, 144, 217),              # RGB 0-255, default blue
        alpha       = 0.35,                        # 0.0 transparent – 1.0 opaque
    )
    canvas.create_image(ox, oy, anchor=NW, image=tk_image)
"""

from __future__ import annotations

import io
import tkinter as tk
from PIL import Image, ImageDraw

# Default selection blue — matches _HL_FILL in select_tool but as RGB ints
_DEFAULT_COLOR = (74, 144, 217)
_DEFAULT_ALPHA = 0.35


def composite_selection(
    ppm_bytes: bytes,
    rects: list[tuple[float, float, float, float]],
    scale: float,
    color: tuple[int, int, int] = _DEFAULT_COLOR,
    alpha: float = _DEFAULT_ALPHA,
) -> tk.PhotoImage:
    """
    Blend a list of semi-transparent highlight rectangles onto a page image.

    Parameters
    ----------
    ppm_bytes : bytes
        Raw PPM output from PDFPage.render_to_ppm().
    rects : list of (x0, y0, x1, y1)
        Selection rectangles in PDF user-space points (not scaled).
    scale : float
        The scale factor used to render ppm_bytes (same as ctx.scale).
        Used to convert PDF points → image pixels.
    color : (R, G, B) ints 0-255
        Highlight colour.  Defaults to a pleasant selection blue.
    alpha : float 0.0-1.0
        Opacity of the highlight layer.  0.35 looks natural.

    Returns
    -------
    tk.PhotoImage
        A new PhotoImage with the highlight baked in, ready for the canvas.
    """
    # Decode PPM → RGBA so we can composite
    base = Image.open(io.BytesIO(ppm_bytes)).convert("RGBA")

    if not rects:
        # No selection — skip compositing entirely
        return _pil_to_photoimage(base)

    # Build a transparent overlay the same size as the page image
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    fill_a = int(alpha * 255)
    fill   = (*color, fill_a)          # RGBA

    for x0, y0, x1, y1 in rects:
        # Convert PDF points to image pixels
        px0 = int(x0 * scale)
        py0 = int(y0 * scale)
        px1 = int(x1 * scale)
        py1 = int(y1 * scale)

        # Guard against degenerate rects
        if px1 <= px0:
            px1 = px0 + 1
        if py1 <= py0:
            py1 = py0 + 1

        draw.rectangle([px0, py0, px1, py1], fill=fill)

    # Alpha-composite the overlay onto the base image
    composited = Image.alpha_composite(base, overlay)

    return _pil_to_photoimage(composited)


def ppm_to_photoimage(ppm_bytes: bytes) -> tk.PhotoImage:
    """
    Convert raw PPM bytes directly to a tk.PhotoImage (no highlighting).
    Drop-in replacement for ``tk.PhotoImage(data=ppm_bytes)`` that avoids
    Tkinter's slow built-in PPM decoder on large pages.
    """
    return tk.PhotoImage(data=ppm_bytes)


# ── internal ──────────────────────────────────────────────────────────────────

def _pil_to_photoimage(img: Image.Image) -> tk.PhotoImage:
    """Convert a PIL Image to tk.PhotoImage via PNG bytes in memory."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return tk.PhotoImage(data=buf.getvalue())