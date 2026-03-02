import os
from src.imaging.image_processor import ImageProcessor
from src.utils.file_utils import save_bytes_to_file, ensure_directory_exists
from src.core.document import PDFDocument

class ImageService:
    """
    Handles higher-level business logic for image extraction and manipulation.
    Coordinates between the Core PDF layer and the Imaging layer.
    """
    def __init__(self):
        self.processor = ImageProcessor()

    def extract_images(self, document: PDFDocument, output_dir: str):
        """
        Iterates through the PDF, extracts all images, and saves them to disk.
        """
        ensure_directory_exists(output_dir)

        for i in range(document.page_count):
            page = document.get_page(i)
            images = page.list_images()

            for idx, img in enumerate(images):
                xref = img[0] # The cross-reference number is the first item
                data = document.extract_image_by_xref(xref)

                # Format: page_1_1.png
                filename = f"page_{i+1}_{idx+1}.{data['ext']}"
                path = os.path.join(output_dir, filename)

                # Use the isolated file utility
                save_bytes_to_file(data["image"], path)

    def rotate_extracted_image(self, path: str, angle: int):
        """Rotates an image file on disk using the Imaging wrapper."""
        image = self.processor.open(path)
        rotated = self.processor.rotate(image, angle)
        self.processor.save(rotated, path)

    def resize_image(self, path: str, size: tuple[int, int]):
        """Resizes an image file on disk using the Imaging wrapper."""
        image = self.processor.open(path)
        resized = self.processor.resize(image, size)
        self.processor.save(resized, path)

    def extract_single_image(self, document: PDFDocument, xref: int, output_path: str):
        """Extracts a single image by its xref and saves it to the output path."""
        data = document.extract_image_by_xref(xref)
        
        # Ensure the user's output path has the correct extension
        ext = data['ext']
        if not output_path.lower().endswith(f".{ext}"):
            output_path = f"{output_path}.{ext}"
            
        save_bytes_to_file(data["image"], output_path)