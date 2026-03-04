# src/services/image_conversion.py
import fitz

class ImageConversionService:
    """Handles the conversion of image files into a PDF document."""

    def convert_images_to_pdf(self, image_paths: list[str], output_path: str) -> bool:
        """
        Creates a new PDF where each image in image_paths is placed on its own page.
        """
        if not image_paths:
            return False

        new_doc = fitz.open()
        try:
            for img_path in image_paths:
                img_doc = fitz.open(img_path)
                pdf_bytes = img_doc.convert_to_pdf()
                img_pdf = fitz.open("pdf", pdf_bytes)
                
                new_doc.insert_pdf(img_pdf)
                
                img_doc.close()
                img_pdf.close()

            new_doc.save(output_path, garbage=4, deflate=True)
            return True
        except Exception as e:
            print(f"Error during image conversion: {e}")
            return False
        finally:
            new_doc.close()

    def get_image_thumbnail(self, image_path: str, width: int = 150) -> bytes:
        """
        Generates a small PPM byte-stream for previewing an image file.
        """
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