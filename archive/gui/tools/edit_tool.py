import tkinter as tk
import tkinter.font as tkFont

from src.gui.tools.base_tool import BaseTool
from src.gui.widgets.edit_overlay import EditOverlay
from src.commands.edit_text_command import EditTextCommand, RichText
from src.utils.paragraph_grouper import (
    group_page_spans,
    paragraph_bbox,
    paragraph_line_spacing,
    hit_test,
)
from src.gui.theme import PAD_XL


# ──────────────────────────────────────────────────────────────────────────────
# Debug helpers
# ──────────────────────────────────────────────────────────────────────────────

def _debug_span(span: dict, scale: float) -> None:
    font_raw  = span.get("font", "N/A")
    size      = span.get("size", 0)
    flags     = span.get("flags", 0)
    color     = span.get("color", 0)
    origin    = span.get("origin", None)
    bbox      = span.get("bbox", None)
    ascender  = span.get("ascender",  "N/A")
    descender = span.get("descender", "N/A")
    text_snip = span.get("text", "")[:40]
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


def _debug_tkfont(family: str, pixel_size: int) -> None:
    print("  ── TKINTER FONT ─────────────────────────────────────")
    print(f"    requested family : {family!r}  pixel_size={pixel_size}")
    try:
        f       = tkFont.Font(family=family, size=pixel_size)
        actual  = f.actual()
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


# ──────────────────────────────────────────────────────────────────────────────
# Rich-text builder
# ──────────────────────────────────────────────────────────────────────────────

def _build_rich_text(para_spans: list[dict]) -> RichText:
    """
    Convert a flat list of paragraph spans (from paragraph_grouper) into the
    RichText wire format:  list[list[tuple[str, int]]].

    Spans that share the same baseline y (within 0.5 pt) are grouped onto the
    same RichText line, so a line like "Hello <bold>world</bold>" — which
    PyMuPDF emits as two spans with the same origin y — is kept together.
    """
    if not para_spans:
        return [[("", 0)]]

    rich: RichText = []
    current_line: list[tuple[str, int]] = []
    current_baseline: float | None = None

    for span in para_spans:
        baseline = round(span["origin"][1], 1)
        flags    = span.get("flags", 0)
        text     = span.get("text", "")

        if current_baseline is None or abs(baseline - current_baseline) <= 0.5:
            current_baseline = baseline
            current_line.append((text, flags))
        else:
            if current_line:
                rich.append(current_line)
            current_line     = [(text, flags)]
            current_baseline = baseline

    if current_line:
        rich.append(current_line)

    return rich if rich else [[("", 0)]]


# ──────────────────────────────────────────────────────────────────────────────
# Tool
# ──────────────────────────────────────────────────────────────────────────────

class EditTextTool(BaseTool):

    def __init__(self, ctx, text_service, redaction_service):
        super().__init__(ctx)
        self.text_service      = text_service
        self.redaction_service = redaction_service
        self.current_overlay   = None
        # Cache paragraphs per page — re-parsed only after an edit or page change
        self._para_cache: dict[int, list[list[dict]]] = {}

    def activate(self):
        self.ctx.canvas.config(cursor="ibeam")

    def deactivate(self):
        if self.current_overlay:
            self.current_overlay.destroy_overlay()
            self.current_overlay = None
        self._para_cache.clear()

    # ------------------------------------------------------------------
    # Click handler
    # ------------------------------------------------------------------

    def on_click(self, canvas_x: float, canvas_y: float):
        if self.current_overlay:
            self.ctx.canvas.focus_set()
            return

        p, ox, oy = self._resolve_page_and_offsets(canvas_y)
        if not self.ctx.doc:
            return

        page       = self.ctx.doc.get_page(p)
        page_width = page.width

        s     = self.ctx.scale
        pdf_x = (canvas_x - ox) / s
        pdf_y = (canvas_y - oy) / s

        # ── Get (or compute) paragraphs for this page ──────────────────────
        if p not in self._para_cache:
            self._para_cache[p] = group_page_spans(page)
        paragraphs = self._para_cache[p]

        # ── Find the paragraph the user clicked ───────────────────────────
        clicked_para: list[dict] | None = None
        for para in paragraphs:
            if hit_test(pdf_x, pdf_y, para):
                clicked_para = para
                break

        if not clicked_para:
            return

        # ── Shared metrics from first span ────────────────────────────────
        first_span = clicked_para[0]

        font_name = first_span.get("font", "helv")
        if "+" in font_name:
            font_name = font_name.split("+")[1]

        font_size  = first_span.get("size", 12.0)
        origin     = first_span.get("origin", None)
        baseline_y = origin[1] if origin else None

        srgb      = first_span.get("color", 0)
        r         = (srgb >> 16) & 0xFF
        g         = (srgb >>  8) & 0xFF
        b         =  srgb        & 0xFF
        color_hex = f"#{r:02x}{g:02x}{b:02x}"
        color_rgb = (r / 255.0, g / 255.0, b / 255.0)

        original_rich = _build_rich_text(clicked_para)
        bbox          = paragraph_bbox(clicked_para)
        line_spacing  = paragraph_line_spacing(clicked_para)
        print(f"  paragraph_bbox = {bbox}")
        print(f"  baseline_y     = {baseline_y}")
        print(f"  all span origins: {[sp['origin'] for sp in clicked_para]}")

        # ── Debug output ───────────────────────────────────────────────────
        print("\n" + "═" * 60)
        print(f"  EDIT TOOL CLICK  page={p}  pdf_xy=({pdf_x:.1f}, {pdf_y:.1f})")
        print(f"  scale={s}  ox={ox}  oy={oy}")
        print(f"  paragraph bbox : {bbox}")
        print(f"  paragraph spans: {len(clicked_para)}  →  {len(original_rich)} rich lines")
        _debug_span(first_span, s)
        _debug_tkfont(font_name, -max(8, round(font_size * s)))
        print(f"  FINAL line_spacing = {line_spacing:.4f}  (baseline-to-baseline)")
        print(f"  FINAL font_name    = {font_name!r}")
        print(f"  FINAL font_size    = {font_size}")
        print(f"  FINAL baseline_y   = {baseline_y}")
        print("═" * 60 + "\n")

        def on_commit(new_rich: RichText, pdf_bbox: tuple):
            self.current_overlay = None
            self._para_cache.pop(p, None)

            print("\n=== ON_COMMIT DEBUG ===")
            print(f"  original_rich: {original_rich}")
            print(f"  new_rich:      {new_rich}")
            original_plain = "\n".join("".join(t for t, _ in ln) for ln in original_rich)
            new_plain      = "\n".join("".join(t for t, _ in ln) for ln in new_rich)
            print(f"  original_plain: {original_plain!r}")
            print(f"  new_plain:      {new_plain!r}")
            print(f"  plains_equal:   {new_plain == original_plain}")
            print(f"  rich_equal:     {new_rich == original_rich}")
            print("=== END ON_COMMIT DEBUG ===\n")
            if new_plain == original_plain and new_rich == original_rich:
                return

            cmd = EditTextCommand(
                self.redaction_service,
                self.text_service,
                self.ctx.doc,
                p,
                pdf_bbox,
                new_rich,
                original_rich,
                font_name,
                font_size,
                color_rgb,
                line_spacing,
                baseline_y,
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
            pdf_bbox     = bbox,
            rich_text    = original_rich,
            font_family  = font_name,
            font_size    = font_size,
            color_hex    = color_hex,
            scale_factor = s,
            ox           = ox,
            oy           = oy,
            on_commit    = on_commit,
            baseline_y   = baseline_y,
            page_width   = page_width,
            line_spacing = line_spacing,
        )

    # ------------------------------------------------------------------
    # Page / offset resolution (unchanged)
    # ------------------------------------------------------------------

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

