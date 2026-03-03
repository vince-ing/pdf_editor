from src.commands.base import Command


class InsertTextCommand(Command):
    """Command to insert text onto a specific page at a point."""

    def __init__(
        self,
        text_service,
        document,
        page_index: int,
        text: str,
        position: tuple,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple = (0, 0, 0),
    ):
        self.text_service = text_service
        self.document = document
        self.page_index = page_index
        self.text = text
        self.position = position
        self.fontsize = fontsize
        self.fontname = fontname
        self.color = color

    def execute(self):
        self.text_service.insert_text(
            self.document,
            self.page_index,
            self.text,
            self.position,
            self.fontsize,
            self.fontname,
            self.color,
        )

    def undo(self):
        raise NotImplementedError(
            "Undo for text insertion requires document state snapshots."
        )


class InsertTextBoxCommand(Command):
    """Command to insert text into a bounding box on a specific page."""

    def __init__(
        self,
        text_service,
        document,
        page_index: int,
        rect: tuple,
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple = (0, 0, 0),
        align: int = 0,
    ):
        self.text_service = text_service
        self.document = document
        self.page_index = page_index
        self.rect = rect
        self.text = text
        self.fontsize = fontsize
        self.fontname = fontname
        self.color = color
        self.align = align

    def execute(self) -> float:
        return self.text_service.insert_textbox(
            self.document,
            self.page_index,
            self.rect,
            self.text,
            self.fontsize,
            self.fontname,
            self.color,
            self.align,
        )

    def undo(self):
        raise NotImplementedError(
            "Undo for text insertion requires document state snapshots."
        )