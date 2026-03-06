from __future__ import annotations
from src.commands.base import Command

class EditTextCommand(Command):
    """
    Executes a true in-place text edit by seamlessly redacting the original 
    paragraph bounding box and rewriting the new string in its place.
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
        lineheight: float = 1.2 # NEW ARGUMENT
    ):
        self.redaction_service = redaction_service
        self.text_service = text_service
        self.document = document
        self.page_index = page_index
        self.original_bbox = original_bbox
        self.new_text = new_text
        self.original_text = original_text
        self.fontname = fontname
        self.fontsize = fontsize
        self.color = color
        self.lineheight = lineheight

    def execute(self) -> None:
        self.redaction_service.add_redaction(
            self.document,
            self.page_index,
            self.original_bbox,
            fill_color=None  
        )
        
        font = self.fontname.lower()
        if font not in ["helv", "cour", "tiro", "zadb", "symb"]:
            font = "helv"
            
        x0, y0, x1, y1 = self.original_bbox
        safe_bbox = (x0, y0, x1 + 20, y1 + 100)
            
        # FIX: Pass the exact lineheight to prevent vertical expansion
        self.text_service.insert_textbox(
            self.document,
            self.page_index,
            safe_bbox,
            self.new_text,
            fontsize=self.fontsize,
            fontname=font,
            color=self.color,
            lineheight=self.lineheight 
        )

    def undo(self) -> None:
        x0, y0, x1, y1 = self.original_bbox
        safe_bbox = (x0, y0, x1 + 20, y1 + 100)
        
        self.redaction_service.add_redaction(
            self.document,
            self.page_index,
            safe_bbox,
            fill_color=None  
        )
        
        font = self.fontname.lower()
        if font not in ["helv", "cour", "tiro", "zadb", "symb"]:
            font = "helv"
            
        # Pass the exact lineheight on Undo as well
        self.text_service.insert_textbox(
            self.document,
            self.page_index,
            safe_bbox,
            self.original_text,
            fontsize=self.fontsize,
            fontname=font,
            color=self.color,
            lineheight=self.lineheight
        )