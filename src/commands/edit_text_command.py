from __future__ import annotations
from src.commands.base import Command


class EditTextCommand(Command):
    """
    Executes a true in-place text edit by redacting the original paragraph
    bounding box and rewriting the new string in its place.
    """

    def __init__(
        self,
        redaction_service,
        text_service,
        document,
        page_index: int,
        original_bbox: tuple[float, float, float, float],
        new_text: str,
        original_text: str,
        fontname: str,
        fontsize: float,
        color: tuple[float, float, float],
        lineheight: float = 1.2,
        fontflags: int = 0,
        baseline_y: float | None = None,
    ):
        self.redaction_service = redaction_service
        self.text_service      = text_service
        self.document          = document
        self.page_index        = page_index
        self.original_bbox     = original_bbox
        self.new_text          = new_text
        self.original_text     = original_text
        self.fontname          = fontname
        self.fontsize          = fontsize
        self.color             = color
        self.lineheight        = lineheight
        self.fontflags         = fontflags
        self.baseline_y        = baseline_y

        self._font = self._resolve_pymupdf_font(fontname, fontflags)

    def _resolve_pymupdf_font(self, base_name: str, flags: int) -> str:
        """Maps PDF font names and flag bits to PyMuPDF built-in Base-14 fonts."""
        name = base_name.lower()
        is_bold = bool(flags & (1 << 4))
        is_italic = bool(flags & (1 << 1))

        if "times" in name or "tiro" in name:
            if is_bold and is_italic: return "tibi"
            if is_bold: return "tibo"
            if is_italic: return "tiit"
            return "tiro"
        elif "courier" in name or "cour" in name:
            if is_bold and is_italic: return "cobi"
            if is_bold: return "cobo"
            if is_italic: return "coit"
            return "cour"
        elif "symbol" in name or "symb" in name:
            return "symb"
        elif "zapf" in name or "zadb" in name:
            return "zadb"
        else: 
            # Default to Helvetica / Arial
            if is_bold and is_italic: return "hebi"
            if is_bold: return "hebo"
            if is_italic: return "heit"
            return "helv"

    def execute(self) -> None:
        self._write(self.new_text)

    def undo(self) -> None:
        self._write(self.original_text)

    def _write(self, text: str) -> None:
        self.redaction_service.add_redaction(
            self.document,
            self.page_index,
            self.original_bbox,
            fill_color=(1.0, 1.0, 1.0),
        )
        
        # Split text into explicit lines based on the \n from the original paragraph 
        # (or the user's new hard line breaks)
        lines = text.split("\n")
        x0 = self.original_bbox[0]
        
        for i, line in enumerate(lines):
            if self.baseline_y is not None:
                # First line sits exactly on original baseline, subsequent lines offset 
                # by the exact line spacing multiplier
                current_baseline = self.baseline_y + (i * self.fontsize * self.lineheight)
            else:
                # Safe fallback if origin data was missing
                current_baseline = self.original_bbox[1] + (self.fontsize * 0.8) + (i * self.fontsize * self.lineheight)
                
            if line.strip():
                self.text_service.insert_text(
                    self.document,
                    self.page_index,
                    line,
                    position=(x0, current_baseline),
                    fontsize=self.fontsize,
                    fontname=self._font,
                    color=self.color,
                )