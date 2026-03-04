import fitz
from src.commands.base import Command


def _snapshot_doc(doc) -> bytes:
    """
    Serialize the entire fitz document to bytes.
    Called *before* execute() so undo can restore the exact prior state.
    """
    return doc._doc.write()


def _restore_doc(doc, snapshot: bytes):
    """
    Replace the live fitz document with one reopened from the snapshot bytes.
    Swaps doc._doc in place so all other references to `doc` stay valid.
    """
    old = doc._doc
    doc._doc = fitz.open("pdf", snapshot)
    if not old.is_closed:
        old.close()


class InsertTextCommand(Command):
    """
    Insert text onto a page.  Undo restores the full document from a
    pre-execute snapshot — simple, reliable, no xref manipulation.
    """

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
        self.document     = document
        self.page_index   = page_index
        self.text         = text
        self.position     = position
        self.fontsize     = fontsize
        self.fontname     = fontname
        self.color        = color
        self._snapshot    = _snapshot_doc(document)

    def execute(self):
        self.text_service.insert_text(
            self.document, self.page_index, self.text,
            self.position, self.fontsize, self.fontname, self.color,
        )

    def undo(self):
        _restore_doc(self.document, self._snapshot)


class InsertTextBoxCommand(Command):
    """Insert text into a bounding box.  Undo via document snapshot."""

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
        self.document     = document
        self.page_index   = page_index
        self.rect         = rect
        self.text         = text
        self.fontsize     = fontsize
        self.fontname     = fontname
        self.color        = color
        self.align        = align
        self._snapshot    = _snapshot_doc(document)

    def execute(self) -> float:
        return self.text_service.insert_textbox(
            self.document, self.page_index, self.rect, self.text,
            self.fontsize, self.fontname, self.color, self.align,
        )

    def undo(self):
        _restore_doc(self.document, self._snapshot)