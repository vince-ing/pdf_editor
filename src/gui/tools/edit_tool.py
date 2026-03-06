import tkinter as tk
import tkinter.font as tkFont

from src.gui.tools.base_tool import BaseTool
from src.gui.widgets.edit_overlay import EditOverlay
from src.commands.edit_text_command import EditTextCommand
from src.gui.theme import PAD_XL


def _debug_span(span: dict, scale: float) -> None:
    """Print every field PyMuPDF gives us for a span, plus derived values."""
    font_raw   = span.get("font", "N/A")
    size       = span.get("size", 0)
    flags      = span.get("flags", 0)
    color      = span.get("color", 0)
    origin     = span.get("origin", None)
    bbox       = span.get("bbox", None)
    ascender   = span.get("ascender",  "N/A")   # relative, e.g. 0.905
    descender  = span.get("descender", "N/A")   # relative, e.g. -0.212
    text_snip  = span.get("text", "")[:40]

    pixel_size = -max(8, round(size * scale))

    print("  ── SPAN ─────────────────────────────────────────────")
    print(f"    font (raw)   : {font_raw!r}")
    print(f"    size (pt)    : {size}")
    print(f"    flags        : {flags:#010b}  ({flags})")
    print(f"      bold?      : {bool(flags & (1 << 4))}")
    print(f"      italic?    : {bool(flags & (1 << 1))}")
    print(f"    color (int)  : {color}  →  #{color:06x}")
    print(f"    origin       : {origin}")
    print(f"    bbox         : {bbox}")
    print(f"    ascender     : {ascender}  (rel, ×size = {size * ascender if isinstance(ascender, float) else 'N/A':.3f} pt)")
    print(f"    descender    : {descender}  (rel, ×size = {size * descender if isinstance(descender, float) else 'N/A':.3f} pt)")
    print(f"    pixel_size   : {pixel_size}  (= -round({size} × {scale}))")
    print(f"    text snippet : {text_snip!r}")


def _debug_line_spacing(lines: list, font_size: float) -> tuple[float, str]:
    """
    Compute line spacing two ways and print both so we can see which is right.
    Returns (spacing_value, method_used).
    """
    print("  ── LINE SPACING ─────────────────────────────────────")
    if len(lines) < 2:
        h = lines[0]["bbox"][3] - lines[0]["bbox"][1] if lines else font_size
        ratio = h / font_size if font_size else 1.2
        print(f"    single line — bbox height={h:.3f}  ratio={ratio:.4f}")
        return ratio, "single-line bbox height"

    # Method A: bbox top to bbox top (old, wrong)
    bbox_y0 = lines[0]["bbox"][1]
    bbox_y1 = lines[1]["bbox"][1]
    bbox_gap = bbox_y1 - bbox_y0
    bbox_ratio = bbox_gap / font_size if font_size else 1.2

    # Method B: baseline (origin) to baseline
    try:
        orig_y0 = lines[0]["spans"][0]["origin"][1]
        orig_y1 = lines[1]["spans"][0]["origin"][1]
        orig_gap   = orig_y1 - orig_y0
        orig_ratio = orig_gap / font_size if font_size else 1.2
        has_origin = True
    except (KeyError, IndexError, TypeError):
        orig_gap   = None
        orig_ratio = None
        has_origin = False

    print(f"    bbox[1] line0={bbox_y0:.3f}  line1={bbox_y1:.3f}")
    print(f"    bbox gap      = {bbox_gap:.3f} pt  →  ratio = {bbox_ratio:.4f}  (OLD/WRONG: includes ascender)")
    if has_origin:
        print(f"    origin[1] line0={orig_y0:.3f}  line1={orig_y1:.3f}")
        print(f"    baseline gap  = {orig_gap:.3f} pt  →  ratio = {orig_ratio:.4f}  (CORRECT: baseline-to-baseline)")
        return orig_ratio, "baseline-to-baseline"
    else:
        print("    origin not available — falling back to bbox method")
        return bbox_ratio, "bbox-top (origin missing)"


def _debug_tkfont(family: str, pixel_size: int) -> None:
    """Create the tkFont we'll actually use and print its metrics."""
    print("  ── TKINTER FONT ─────────────────────────────────────")
    print(f"    requested family : {family!r}  pixel_size={pixel_size}")
    try:
        f = tkFont.Font(family=family, size=pixel_size)
        actual = f.actual()
        metrics = f.metrics()
        print(f"    actual family    : {actual.get('family')!r}")
        print(f"    actual size      : {actual.get('size')}")
        print(f"    actual weight    : {actual.get('weight')}")
        print(f"    actual slant     : {actual.get('slant')}")
        print(f"    metrics ascent   : {metrics['ascent']} px")
        print(f"    metrics descent  : {metrics['descent']} px")
        print(f"    metrics linespace: {metrics['linespace']} px")
        print(f"    metrics fixed    : {metrics['fixed']}")
    except Exception as e:
        print(f"    ERROR: {e}")


class EditTextTool(BaseTool):

    def __init__(self, ctx, text_service, redaction_service):
        super().__init__(ctx)
        self.text_service      = text_service
        self.redaction_service = redaction_service
        self.current_overlay   = None

    def activate(self):
        self.ctx.canvas.config(cursor="ibeam")

    def deactivate(self):
        if self.current_overlay:
            self.current_overlay.destroy_overlay()
            self.current_overlay = None

    def on_click(self, canvas_x: float, canvas_y: float):
        if self.current_overlay:
            self.ctx.canvas.focus_set()
            return

        p, ox, oy = self._resolve_page_and_offsets(canvas_y)
        if not self.ctx.doc:
            return

        page      = self.ctx.doc.get_page(p)
        page_dict = page.get_text_dict()

        s     = self.ctx.scale
        pdf_x = (canvas_x - ox) / s
        pdf_y = (canvas_y - oy) / s

        clicked_block = None
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            x0, y0, x1, y1 = block.get("bbox", [0, 0, 0, 0])
            if x0 <= pdf_x <= x1 and y0 <= pdf_y <= y1:
                clicked_block = block
                break

        if not clicked_block:
            return

        first_span = None
        for line in clicked_block.get("lines", []):
            if line.get("spans"):
                first_span = line["spans"][0]
                break

        if not first_span:
            return

        full_text = ""
        for line in clicked_block.get("lines", []):
            for span in line.get("spans", []):
                full_text += span.get("text", "")
            full_text += "\n"
        full_text = full_text.strip()

        font_name  = first_span.get("font", "helv")
        if "+" in font_name:
            font_name = font_name.split("+")[1]

        font_size  = first_span.get("size", 12)
        font_flags = first_span.get("flags", 0)
        origin     = first_span.get("origin", None)
        baseline_y = origin[1] if origin else None

        srgb      = first_span.get("color", 0)
        r         = (srgb >> 16) & 0xFF
        g         = (srgb >>  8) & 0xFF
        b         =  srgb        & 0xFF
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        color_rgb = (r / 255.0, g / 255.0, b / 255.0)

        lines = clicked_block.get("lines", [])

        # ── FULL DEBUG OUTPUT ─────────────────────────────────────────────────
        print("\n" + "═" * 60)
        print(f"  EDIT TOOL CLICK  page={p}  pdf_xy=({pdf_x:.1f}, {pdf_y:.1f})")
        print(f"  scale={s}  ox={ox}  oy={oy}")
        print(f"  block bbox: {clicked_block['bbox']}")
        print(f"  line count: {len(lines)}")
        _debug_span(first_span, s)

        pixel_size_for_debug = -max(8, round(font_size * s))
        _debug_tkfont(font_name, pixel_size_for_debug)

        line_spacing, spacing_method = _debug_line_spacing(lines, font_size)
        line_spacing = max(0.8, min(2.5, line_spacing))

        print(f"  FINAL line_spacing = {line_spacing:.4f}  (method: {spacing_method})")
        print(f"  FINAL font_name    = {font_name!r}")
        print(f"  FINAL font_size    = {font_size}")
        print(f"  FINAL baseline_y   = {baseline_y}")
        print("═" * 60 + "\n")
        # ─────────────────────────────────────────────────────────────────────

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
                line_spacing,
            )
            try:
                cmd.execute()
            except Exception as ex:
                self.ctx.flash_status(f"✗ Edit failed: {ex}", color="#e06c75")
                print(f"EditTextCommand.execute() failed: {ex}")
                return
            self.ctx.push_history(cmd)
            self.ctx.invalidate_cache(p)
            self.ctx.render()
            self.ctx.flash_status("✓ Text updated")

        self.current_overlay = EditOverlay(
            canvas       = self.ctx.canvas,
            pdf_bbox     = clicked_block["bbox"],
            text         = full_text,
            font_family  = font_name,
            font_size    = font_size,
            color_hex    = color_hex,
            scale_factor = s,
            ox           = ox,
            oy           = oy,
            on_commit    = on_commit,
            baseline_y   = baseline_y,
            font_flags   = font_flags,
        )

    def _resolve_page_and_offsets(self, cy: float) -> tuple[int, float, float]:
        editor = self.ctx._editor
        if getattr(editor, "_continuous_mode", False) and self.ctx.doc:
            page_idx = editor._cont_page_at_y(cy)
            oy       = editor._cont_page_top(page_idx)
            try:
                p  = self.ctx.doc.get_page(page_idx)
                iw = int(p.width * self.ctx.scale)
                cw = getattr(editor, "_cont_cw", self.ctx.canvas.winfo_width())
                ox = max(PAD_XL, (cw - iw) // 2)
            except Exception:
                ox = self.ctx.page_offset_x
            return page_idx, ox, oy
        return self.ctx.current_page, self.ctx.page_offset_x, self.ctx.page_offset_y