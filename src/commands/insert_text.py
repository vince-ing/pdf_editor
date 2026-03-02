from src.commands.base import Command

class InsertTextCommand(Command):
    """Command to insert text onto a specific page."""
    
    def __init__(self, text_service, document, page_index: int, text: str, position: tuple[float, float], fontsize: int = 12):
        self.text_service = text_service
        self.document = document
        self.page_index = page_index
        self.text = text
        self.position = position
        self.fontsize = fontsize

    def execute(self):
        self.text_service.insert_text(
            self.document,
            self.page_index,
            self.text,
            self.position,
            self.fontsize
        )

    def undo(self):
        """
        PyMuPDF bakes text into the document structure, making a strict 'undo' difficult
        without a full document state backup. Left as a stub for future state-snapshot implementation.
        """
        raise NotImplementedError("Undo for text insertion requires document state snapshots.")