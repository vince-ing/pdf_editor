# src/services/image_conversion.py
import os
import io
import fitz
import pytesseract
from PIL import Image

# Dynamically resolve the path to tesseract.exe based on this file's location
# __file__ is src/services/image_conversion.py
# 2 levels up is the project root (pdf_editor)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
TESSERACT_EXE_PATH = os.path.join(PROJECT_ROOT, "pytesseract", "tesseract.exe")

if os.path.exists(TESSERACT_EXE_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE_PATH

class ImageConversionService:
    """Handles the conversion of image files into a PDF document."""

    def convert_images_to_pdf(self, image_paths: list[str], output_path: str, apply_ocr: bool = False) -> bool:
        """
        Creates a new PDF where each image in image_paths is placed on its own page.
        If apply_ocr is True, generates a searchable text layer.
        """
        if not image_paths:
            return False

        new_doc = fitz.open()
        try:
            for img_path in image_paths:
                if apply_ocr:
                    # pytesseract generates a PDF byte string with the image + hidden text layer
                    pdf_bytes = pytesseract.image_to_pdf_or_hocr(img_path, extension='pdf')
                    img_pdf = fitz.open("pdf", pdf_bytes)
                else:
                    img_doc = fitz.open(img_path)
                    pdf_bytes = img_doc.convert_to_pdf()
                    img_pdf = fitz.open("pdf", pdf_bytes)
                    img_doc.close()
                
                new_doc.insert_pdf(img_pdf)
                img_pdf.close()

            new_doc.save(output_path, garbage=4, deflate=True)
            return True
        except Exception as e:
            print(f"Error during image conversion: {e}")
            return False
        finally:
            new_doc.close()

    def get_image_thumbnail(self, image_path: str, width: int = 150) -> bytes:
        """Generates a small PPM byte-stream for previewing an image file."""
        try:
            img_doc = fitz.open(image_path)
            page = img_doc[0]
            scale = width / page.rect.width
            matrix = fitz.Matrix(scale, scale)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img_bytes = pix.tobytes("ppm")
            img_doc.close()
            return img_bytes
        except Exception:
            return b""