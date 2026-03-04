# src/commands/convert_images.py
from src.commands.base import Command

class ConvertImagesToPdfCommand(Command):
    """
    Generates a new PDF from a list of image paths.
    Undo is a no-op as it does not modify an active document state.
    """

    def __init__(self, conversion_service, image_paths: list[str], output_path: str):
        self.conversion_service = conversion_service
        self.image_paths = image_paths
        self.output_path = output_path
        self.success = False

    def execute(self):
        self.success = self.conversion_service.convert_images_to_pdf(
            self.image_paths, self.output_path
        )

    def undo(self):
        pass

    def cleanup(self):
        pass