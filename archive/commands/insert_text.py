from __future__ import annotations

from src.commands.base import Command
from src.commands.snapshot import DocumentSnapshot
from src.core.document import PDFDocument
from src.services.text_service import TextService


class InsertTextCommand(Command):
    """
    Insert text onto a page.

    Undo restores the full document from a pre-execute snapshot stored on
    disk (via DocumentSnapshot), keeping RAM usage flat regardless of PDF size.
    """

    def __init__(
        self,
        text_service: TextService,
        document: PDFDocument,
        page_index: int,
        text: str,
        position: tuple[float, float],
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        self.text_service = text_service
        self.document     = document
        self.page_index   = page_index
        self.text         = text
        self.position     = position
        self.fontsize     = fontsize
        self.fontname     = fontname
        self.color        = color
        self._snapshot    = DocumentSnapshot(document)

    def execute(self) -> None:
        self.text_service.insert_text(
            self.document, self.page_index, self.text,
            self.position, self.fontsize, self.fontname, self.color,
        )

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()


class InsertTextBoxCommand(Command):
    """Insert text into a bounding box.  Undo via disk snapshot."""

    def __init__(
        self,
        text_service: TextService,
        document: PDFDocument,
        page_index: int,
        rect: tuple[float, float, float, float],
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple[float, float, float] = (0, 0, 0),
        align: int = 0,
    ) -> None:
        self.text_service = text_service
        self.document     = document
        self.page_index   = page_index
        self.rect         = rect
        self.text         = text
        self.fontsize     = fontsize
        self.fontname     = fontname
        self.color        = color
        self.align        = align
        self._snapshot    = DocumentSnapshot(document)

    def execute(self) -> float:
        return self.text_service.insert_textbox(
            self.document, self.page_index, self.rect, self.text,
            self.fontsize, self.fontname, self.color, self.align,
        )

    def undo(self) -> None:
        self._snapshot.restore(self.document)

    def cleanup(self) -> None:
        self._snapshot.cleanup()