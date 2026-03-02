import fitz

class PDFPage:
    """
    Core wrapper for PyMuPDF (fitz) Page.
    Handles operations specific to a single page.
    """
    def __init__(self, page: fitz.Page):
        self._page = page

    def rotate(self, angle: int):
        """Rotates the page by the specified angle (must be a multiple of 90)."""
        current_rotation = self._page.rotation
        self._page.set_rotation((current_rotation + angle) % 360)

    def insert_text(self, position: tuple[float, float], text: str, fontsize: int = 12):
        """Inserts text at the given (x, y) coordinates."""
        # position is expected as (x, y) starting from top-left
        self._page.insert_text(position, text, fontsize=fontsize)

    def insert_image(self, rect_coords: tuple[float, float, float, float], image_path: str):
        """
        Inserts an image into the defined rectangle boundary.
        :param rect_coords: Tuple of (x0, y0, x1, y1) defining the bounding box.
        """
        rect = fitz.Rect(*rect_coords)
        self._page.insert_image(rect, filename=image_path)

    def list_images(self) -> list[tuple]:
        """
        Returns a list of image metadata tuples on the page.
        The first element of each tuple is the image 'xref' number.
        """
        return self._page.get_images(full=True)
    
    def render_to_ppm(self, scale: float = 1.0) -> bytes:
        """Renders the page to PPM image format bytes (natively supported by Tkinter)."""
        # A matrix allows us to scale (zoom) the visual render for better resolution
        matrix = fitz.Matrix(scale, scale)
        pix = self._page.get_pixmap(matrix=matrix)
        return pix.tobytes("ppm")

    def get_image_info(self) -> list[dict]:
        """
        Returns info about images on the page.
        Includes the 'bbox' (bounding box coordinates) and the 'xref' (image ID).
        """
        return self._page.get_image_info(xrefs=True)