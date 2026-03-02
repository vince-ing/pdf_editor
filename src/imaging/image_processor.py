from PIL import Image

class ImageProcessor:
    """
    Wrapper for Pillow (PIL) to handle image transformations.
    Isolates the image processing library from the rest of the application.
    """
    def open(self, path: str) -> Image.Image:
        """Opens an image from the filesystem."""
        return Image.open(path)

    def rotate(self, image: Image.Image, angle: int) -> Image.Image:
        """
        Rotates an image by the given angle.
        expand=True ensures the image canvas resizes to fit the rotated image,
        preventing the corners from being cropped off.
        """
        return image.rotate(angle, expand=True)

    def resize(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Resizes the image to the specified (width, height) tuple."""
        # Using LANCZOS (formerly ANTIALIAS) for high-quality downsampling
        return image.resize(size, Image.Resampling.LANCZOS)

    def grayscale(self, image: Image.Image) -> Image.Image:
        """Converts the image to grayscale."""
        return image.convert("L")

    def save(self, image: Image.Image, output_path: str, format: str = None):
        """
        Saves the image to the filesystem.
        If format is None, Pillow infers it from the output_path extension.
        """
        image.save(output_path, format=format)