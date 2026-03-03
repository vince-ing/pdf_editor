import fitz


class PDFPage:
    """
    Core wrapper for PyMuPDF (fitz) Page.
    Handles operations specific to a single page.
    """

    def __init__(self, page: fitz.Page):
        self._page = page

    @property
    def width(self) -> float:
        return self._page.rect.width

    @property
    def height(self) -> float:
        return self._page.rect.height

    @property
    def rotation(self) -> int:
        return self._page.rotation

    def rotate(self, angle: int):
        """Rotates the page by the specified angle (must be a multiple of 90)."""
        current = self._page.rotation
        self._page.set_rotation((current + angle) % 360)

    def insert_text(
        self,
        position: tuple,
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple = (0, 0, 0),
    ):
        """
        Inserts text at the given (x, y) coordinates.
        color: RGB tuple with values 0.0–1.0.
        """
        self._page.insert_text(
            position,
            text,
            fontsize=fontsize,
            fontname=fontname,
            color=color,
        )

    def insert_textbox(
        self,
        rect: tuple,
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple = (0, 0, 0),
        align: int = 0,
    ) -> float:
        """
        Inserts text into a bounded rectangle with word-wrapping.
        Returns the unused vertical space (negative if text overflows).
        align: 0=left, 1=center, 2=right, 3=justify
        """
        r = fitz.Rect(*rect)
        return self._page.insert_textbox(
            r,
            text,
            fontsize=fontsize,
            fontname=fontname,
            color=color,
            align=align,
        )

    def insert_image(self, rect_coords: tuple, image_path: str = None, stream: bytes = None):
        """Inserts an image into the defined rectangle boundary."""
        rect = fitz.Rect(*rect_coords)
        kwargs = {}
        if image_path:
            kwargs["filename"] = image_path
        elif stream:
            kwargs["stream"] = stream
        self._page.insert_image(rect, **kwargs)

    def list_images(self) -> list:
        return self._page.get_images(full=True)

    def render_to_ppm(self, scale: float = 1.0, colorspace: str = "rgb") -> bytes:
        """Renders the page to PPM bytes at the given scale factor."""
        matrix = fitz.Matrix(scale, scale)
        pix = self._page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
        return pix.tobytes("ppm")

    def render_to_png_bytes(self, scale: float = 1.0) -> bytes:
        """Renders the page to PNG bytes (higher quality, larger)."""
        matrix = fitz.Matrix(scale, scale)
        pix = self._page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=True)
        return pix.tobytes("png")

    def get_image_info(self) -> list:
        return self._page.get_image_info(xrefs=True)

    def get_text_blocks(self) -> list:
        """Returns text blocks as (x0, y0, x1, y1, text, block_no, block_type)."""
        return self._page.get_text("blocks")

    def get_links(self) -> list:
        return self._page.get_links()

    def search_text(self, query: str) -> list:
        """Returns a list of fitz.Rect instances where the query text is found."""
        return self._page.search_for(query)

    def add_highlight(self, quads):
        """Adds a highlight annotation over the given quads/rects."""
        return self._page.add_highlight_annot(quads)

    def add_rect_annotation(self, rect: tuple, color=(1, 0, 0), fill=None, width: float = 1.5):
        rect_obj = fitz.Rect(*rect)
        annot = self._page.add_rect_annot(rect_obj)
        annot.set_border(width=width)
        annot.set_colors(stroke=color, fill=fill)
        annot.update()
        return annot

    def get_annotations(self) -> list:
        return list(self._page.annots())

    def delete_annotation(self, annot):
        self._page.delete_annot(annot)

    def crop(self, rect: tuple):
        """Crops the page's visible area to the given rect."""
        self._page.set_cropbox(fitz.Rect(*rect))