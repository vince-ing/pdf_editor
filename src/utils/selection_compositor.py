# src/utils/selection_compositor.py

from __future__ import annotations

import io
import tkinter as tk
from PIL import Image, ImageDraw, ImageChops

# Default selection blue
_DEFAULT_COLOR = (74, 144, 217)
_DEFAULT_ALPHA = 0.35


def composite_selection(
    ppm_bytes: bytes,
    rects: list[tuple[float, float, float, float]] = None,
    scale: float = 1.0,
    color: tuple[int, int, int] = _DEFAULT_COLOR,
    alpha: float = _DEFAULT_ALPHA,
    layers: list[dict] = None,
) -> tk.PhotoImage:
    """
    Blend semi-transparent highlight rectangles onto a page image.
    Uses a 'Multiply' blend mode so dark text remains crisp and readable.

    `layers` format: [{"rects": [...], "color": (R, G, B), "alpha": 0.5}, ...]
    """
    # Decode PPM → RGBA
    base = Image.open(io.BytesIO(ppm_bytes)).convert("RGBA")

    if not rects and not layers:
        return _pil_to_photoimage(base)

    all_layers = layers or []
    if rects:
        all_layers.insert(0, {"rects": rects, "color": color, "alpha": alpha})

    result = base
    
    for layer in all_layers:
        layer_alpha = layer.get("alpha", _DEFAULT_ALPHA)
        layer_color = layer.get("color", _DEFAULT_COLOR)
        layer_rects = layer.get("rects", [])
        
        if not layer_rects:
            continue

        # Create a pure white canvas for the multiply effect
        mult_layer = Image.new("RGB", base.size, (255, 255, 255))
        draw = ImageDraw.Draw(mult_layer)
        
        for x0, y0, x1, y1 in layer_rects:
            px0 = int(x0 * scale)
            py0 = int(y0 * scale)
            px1 = int(x1 * scale)
            py1 = int(y1 * scale)

            # Guard against degenerate rects
            if px1 <= px0: px1 = px0 + 1
            if py1 <= py0: py1 = py0 + 1

            draw.rectangle([px0, py0, px1, py1], fill=layer_color)

        # Multiply the color layer with the current image
        # White areas become the layer_color, black areas remain black
        multiplied = ImageChops.multiply(result.convert("RGB"), mult_layer).convert("RGBA")
        
        # Blend the multiplied version over the original based on the alpha value
        # This acts as an "opacity" slider for the multiply effect
        result = Image.blend(result, multiplied, layer_alpha)

    return _pil_to_photoimage(result)


def ppm_to_photoimage(ppm_bytes: bytes) -> tk.PhotoImage:
    """
    Convert raw PPM bytes directly to a tk.PhotoImage (no highlighting).
    """
    return tk.PhotoImage(data=ppm_bytes)


# ── internal ──────────────────────────────────────────────────────────────────

def _pil_to_photoimage(img: Image.Image) -> tk.PhotoImage:
    """Convert a PIL Image to tk.PhotoImage via PNG bytes in memory."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return tk.PhotoImage(data=buf.getvalue())