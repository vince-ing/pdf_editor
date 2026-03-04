"""
ImageService — business logic for image extraction and insertion.
Mirrors the original image_service from the project, extended with insert support.
"""

import os
from src.core.document import PDFDocument
from src.utils.file_utils import save_bytes_to_file, ensure_directory_exists


class ImageService:
    """Handles image extraction and insertion on PDF pages."""

    def extract_images(self, document: PDFDocument, output_dir: str):
        """Extract all images from all pages and save them to output_dir."""
        ensure_directory_exists(output_dir)
        for i in range(document.page_count):
            page = document.get_page(i)
            for idx, img in enumerate(page.list_images()):
                xref = img[0]
                data = document.extract_image_by_xref(xref)
                filename = f"page_{i + 1}_{idx + 1}.{data['ext']}"
                save_bytes_to_file(data["image"], os.path.join(output_dir, filename))

    def extract_single_image(self, document: PDFDocument, xref: int, output_path: str):
        """Extract a single image by xref and save to output_path."""
        data = document.extract_image_by_xref(xref)
        ext  = data["ext"]
        if not output_path.lower().endswith(f".{ext}"):
            output_path = f"{output_path}.{ext}"
        save_bytes_to_file(data["image"], output_path)

    def insert_image(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
        image_path: str,
    ):
        """
        Insert an image file into a rectangular region on a page.
        rect: (x0, y0, x1, y1) in PDF user-space points.
        """
        page = document.get_page(page_index)
        page.insert_image(rect, image_path=image_path)