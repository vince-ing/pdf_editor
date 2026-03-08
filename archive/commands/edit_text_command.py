from __future__ import annotations
import fitz  # PyMuPDF — needed for text_length measurement
from src.commands.base import Command

# ---------------------------------------------------------------------------
# Type alias for the rich-text wire format shared by all three pipeline stages.
#
# RichText = list of lines, each line = list of (text_chunk, font_flags) pairs.
#
#   [
#     [("Hello ", 0), ("world", 16)],   # line 0: "world" is bold
#     [("Some ",  0), ("italic", 2)],   # line 1: "italic" is italic
#   ]
#
# font_flags uses the same bit layout as PyMuPDF span["flags"]:
#   bit 1 (0x02) = italic
#   bit 4 (0x10) = bold
# ---------------------------------------------------------------------------
RichText = list[list[tuple[str, int]]]


class EditTextCommand(Command):
    """
    Executes a true in-place text edit by redacting the original paragraph
    bounding box and rewriting the new rich-text content in its place.

    ``new_rich`` and ``original_rich`` are both ``RichText`` values (see alias
    above).  Each span is drawn independently so that bold / italic words keep
    their own font; PyMuPDF's ``fitz.Font.text_length()`` is used to advance
    the x-cursor between spans so they sit flush against each other.
    """

    def __init__(
        self,
        redaction_service,
        text_service,
        document,
        page_index: int,
        original_bbox: tuple[float, float, float, float],
        new_rich: RichText,
        original_rich: RichText,
        fontname: str,
        fontsize: float,
        color: tuple[float, float, float],
        lineheight: float = 1.2,
        baseline_y: float | None = None,
    ):
        self.redaction_service = redaction_service
        self.text_service      = text_service
        self.document          = document
        self.page_index        = page_index
        self.original_bbox     = original_bbox
        self.new_rich          = new_rich
        self.original_rich     = original_rich
        self.fontname          = fontname
        self.fontsize          = fontsize
        self.color             = color
        self.lineheight        = lineheight
        self.baseline_y        = baseline_y

    # ------------------------------------------------------------------
    # Font helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_pymupdf_font(base_name: str, flags: int) -> str:
        """Maps a PDF font name + flag bits to a PyMuPDF Base-14 font tag."""
        name      = base_name.lower()
        is_bold   = bool(flags & (1 << 4))
        is_italic = bool(flags & (1 << 1))

        if "times" in name or "tiro" in name:
            if is_bold and is_italic: return "tibi"
            if is_bold:               return "tibo"
            if is_italic:             return "tiit"
            return "tiro"
        elif "courier" in name or "cour" in name:
            if is_bold and is_italic: return "cobi"
            if is_bold:               return "cobo"
            if is_italic:             return "coit"
            return "cour"
        elif "symbol" in name or "symb" in name:
            return "symb"
        elif "zapf" in name or "zadb" in name:
            return "zadb"
        else:
            # Default: Helvetica / Arial family
            if is_bold and is_italic: return "hebi"
            if is_bold:               return "hebo"
            if is_italic:             return "heit"
            return "helv"

    @staticmethod
    def _fitz_text_length(text: str, fontname: str, fontsize: float) -> float:
        """
        Return the rendered width of ``text`` in PDF points for the given
        Base-14 font tag and size.  Falls back to a simple character-count
        estimate if fitz raises (e.g. empty string or unknown font tag).
        """
        try:
            font = fitz.Font(fontname=fontname)
            return font.text_length(text, fontsize=fontsize)
        except Exception:
            # Very rough fallback: average ~0.6× em per character
            return len(text) * fontsize * 0.6

    # ------------------------------------------------------------------
    # Command interface
    # ------------------------------------------------------------------

    def execute(self) -> None:
        self._write(self.new_rich)

    def undo(self) -> None:
        self._write(self.original_rich)

    # ------------------------------------------------------------------
    # Word-wrap helper
    # ------------------------------------------------------------------

    def _wrap_spans(
        self,
        spans: list[tuple[str, int]],
        max_width: float,
    ) -> list[list[tuple[str, int]]]:
        """
        Word-wrap a single RichText line (list of styled spans) into multiple
        visual lines that each fit within *max_width* PDF points.

        Splitting is done at space boundaries.  Each token (word + trailing
        space) is measured with the font that applies to it, so bold words —
        which are slightly wider — are accounted for correctly.

        Returns a list of visual lines, each being a list of (text, flags).
        """
        # Flatten to (token, flags) pairs, splitting only on spaces
        tokens: list[tuple[str, int]] = []
        for chunk_text, flags in spans:
            parts = chunk_text.split(" ")
            for i, part in enumerate(parts):
                token = part + (" " if i < len(parts) - 1 else "")
                if token:
                    tokens.append((token, flags))

        visual_lines: list[list[tuple[str, int]]] = []
        current_line: list[tuple[str, int]] = []
        current_width = 0.0

        for token, flags in tokens:
            font     = self._resolve_pymupdf_font(self.fontname, flags)
            token_w  = self._fitz_text_length(token, font, self.fontsize)

            if not current_line or current_width + token_w <= max_width:
                current_line.append((token, flags))
                current_width += token_w
            else:
                visual_lines.append(current_line)
                current_line  = [(token, flags)]
                current_width = token_w

        if current_line:
            visual_lines.append(current_line)

        return visual_lines

    # ------------------------------------------------------------------
    # Core renderer
    # ------------------------------------------------------------------

    def _write(self, rich: RichText) -> None:
        """
        Redact the original bbox then re-draw each styled span with
        word-wrapping so text never overflows horizontally.

        Each RichText line is word-wrapped to fit the original paragraph
        width.  The resulting visual lines are drawn span-by-span with
        ``insert_text``, advancing the x cursor by the measured width of
        each chunk so mixed bold/normal spans sit flush against each other.
        """
        self.redaction_service.add_redaction(
            self.document,
            self.page_index,
            self.original_bbox,
            fill_color=(1.0, 1.0, 1.0),
        )

        x0, _, x1, _ = self.original_bbox
        max_width     = x1 - x0

        # ── Expand RichText lines into word-wrapped visual lines ──────────
        visual_lines: list[list[tuple[str, int]]] = []
        for spans in rich:
            wrapped = self._wrap_spans(spans, max_width)
            visual_lines.extend(wrapped)

        # ── Draw each visual line span-by-span ────────────────────────────
        for line_idx, spans in enumerate(visual_lines):
            if self.baseline_y is not None:
                current_baseline = (
                    self.baseline_y
                    + line_idx * self.fontsize * self.lineheight
                )
            else:
                current_baseline = (
                    self.original_bbox[1]
                    + self.fontsize * 0.8
                    + line_idx * self.fontsize * self.lineheight
                )

            cursor_x = x0
            for chunk_text, chunk_flags in spans:
                if not chunk_text:
                    continue

                pymupdf_font = self._resolve_pymupdf_font(self.fontname, chunk_flags)

                self.text_service.insert_text(
                    self.document,
                    self.page_index,
                    chunk_text,
                    position=(cursor_x, current_baseline),
                    fontsize=self.fontsize,
                    fontname=pymupdf_font,
                    color=self.color,
                )

                cursor_x += self._fitz_text_length(
                    chunk_text, pymupdf_font, self.fontsize
                )