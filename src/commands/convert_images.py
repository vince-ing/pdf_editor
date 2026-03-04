# src/commands/convert_images.py
from src.commands.base import Command

class ConvertImagesToPdfCommand(Command):
    """Generates a new PDF from a list of image paths."""

    def __init__(self, conversion_service, image_paths: list[str], output_path: str, apply_ocr: bool = False):
        self.conversion_service = conversion_service
        self.image_paths = image_paths
        self.output_path = output_path
        self.apply_ocr = apply_ocr
        self.success = False

    def execute(self):
        self.success = self.conversion_service.convert_images_to_pdf(
            self.image_paths, self.output_path, self.apply_ocr
        )

    def undo(self): pass
    def cleanup(self): pass