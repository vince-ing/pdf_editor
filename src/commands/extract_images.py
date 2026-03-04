"""
Image extraction commands.
These are read-only operations — no snapshot needed, cleanup() is a no-op.
"""

from src.commands.base import Command


class ExtractImagesCommand(Command):
    """Extracts all images from a PDF to a target directory."""

    def __init__(self, image_service, document, output_dir: str):
        self.image_service = image_service
        self.document      = document
        self.output_dir    = output_dir

    def execute(self):
        self.image_service.extract_images(self.document, self.output_dir)

    def undo(self):
        pass  # No-op: auto-deleting extracted user files is unsafe


class ExtractSingleImageCommand(Command):
    """Extracts a single image by xref to a file path."""

    def __init__(self, image_service, document, xref: int, output_path: str):
        self.image_service = image_service
        self.document      = document
        self.xref          = xref
        self.output_path   = output_path

    def execute(self):
        self.image_service.extract_single_image(self.document, self.xref, self.output_path)

    def undo(self):
        pass  # No-op: auto-deleting extracted user files is unsafe