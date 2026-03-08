"""
Image extraction commands.
These are read-only operations — no snapshot needed, cleanup() is a no-op.
"""

from __future__ import annotations

from src.commands.base import Command
from src.core.document import PDFDocument
from src.services.image_service import ImageService


class ExtractImagesCommand(Command):
    """Extracts all images from a PDF to a target directory."""

    def __init__(
        self,
        image_service: ImageService,
        document: PDFDocument,
        output_dir: str,
    ) -> None:
        self.image_service = image_service
        self.document      = document
        self.output_dir    = output_dir

    def execute(self) -> None:
        self.image_service.extract_images(self.document, self.output_dir)

    def undo(self) -> None:
        pass  # No-op: auto-deleting extracted user files is unsafe


class ExtractSingleImageCommand(Command):
    """Extracts a single image by xref to a file path."""

    def __init__(
        self,
        image_service: ImageService,
        document: PDFDocument,
        xref: int,
        output_path: str,
    ) -> None:
        self.image_service = image_service
        self.document      = document
        self.xref          = xref
        self.output_path   = output_path

    def execute(self) -> None:
        self.image_service.extract_single_image(self.document, self.xref, self.output_path)

    def undo(self) -> None:
        pass  # No-op: auto-deleting extracted user files is unsafe