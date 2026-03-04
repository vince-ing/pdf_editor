from __future__ import annotations

from src.commands.base import Command
from src.services.image_conversion import ImageConversionService


class ConvertImagesToPdfCommand(Command):
    """Generates a new PDF from a list of image paths."""

    def __init__(
        self,
        conversion_service: ImageConversionService,
        image_paths: list[str],
        output_path: str,
        apply_ocr: bool = False,
    ) -> None:
        self.conversion_service = conversion_service
        self.image_paths        = image_paths
        self.output_path        = output_path
        self.apply_ocr          = apply_ocr
        self.success: bool      = False

    def execute(self) -> None:
        self.success = self.conversion_service.convert_images_to_pdf(
            self.image_paths, self.output_path, self.apply_ocr
        )

    def undo(self) -> None:
        pass  # No-op: creating a new file is not reversible via undo

    def cleanup(self) -> None:
        pass  # No temporary resources to release