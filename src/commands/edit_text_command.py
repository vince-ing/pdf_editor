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

        font = fontname.lower()
        if font not in ["helv", "cour", "tiro", "zadb", "symb"]:
            font = "helv"
        self._font = font

        x0, y0, x1, y1 = original_bbox
        self._write_bbox = (x0, y0, x1 + 20, y1 + 10)

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
        self.text_service.insert_textbox(
            self.document,
            self.page_index,
            self._write_bbox,
            text,
            fontsize=self.fontsize,
            fontname=self._font,
            color=self.color,
            lineheight=self.lineheight,
        )