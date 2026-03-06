from __future__ import annotations

import fitz

_REDACT_IMAGE_PIXELS        = getattr(fitz, "PDF_REDACT_IMAGE_PIXELS",        2)
_REDACT_LINE_ART_IF_COVERED = getattr(fitz, "PDF_REDACT_LINE_ART_IF_COVERED", 1)


class PDFPage:
    """Core wrapper for PyMuPDF (fitz) Page."""

    def __init__(self, page: fitz.Page) -> None:
        self._page: fitz.Page = page

    @property
    def width(self) -> float:
        return self._page.rect.width

    @property
    def height(self) -> float:
        return self._page.rect.height

    @property
    def rotation(self) -> int:
        return self._page.rotation

    def rotate(self, angle: int) -> None:
        current = self._page.rotation
        self._page.set_rotation((current + angle) % 360)

    def insert_text(
        self,
        position: tuple[float, float],
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple[float, float, float] = (0, 0, 0),
    ) -> None:
        self._page.insert_text(
            position, text,
            fontsize=fontsize, fontname=fontname, color=color,
        )

    def insert_textbox(
        self,
        rect: tuple[float, float, float, float],
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple[float, float, float] = (0, 0, 0),
        align: int = 0,
        lineheight: float | None = None,
    ) -> float:
        """
        Inserts text into a bounded rectangle with word-wrapping.
        lineheight is passed to fitz only when not None so older PyMuPDF
        versions that don't support it are unaffected.
        """
        r      = fitz.Rect(*rect)
        kwargs = dict(fontsize=fontsize, fontname=fontname, color=color, align=align)
        if lineheight is not None:
            kwargs["lineheight"] = lineheight
        return self._page.insert_textbox(r, text, **kwargs)

    def insert_image(
        self,
        rect_coords: tuple[float, float, float, float],
        image_path: str | None = None,
        stream: bytes | None = None,
    ) -> None:
        rect   = fitz.Rect(*rect_coords)
        kwargs = {}
        if image_path:
            kwargs["filename"] = image_path
        elif stream:
            kwargs["stream"] = stream
        self._page.insert_image(rect, **kwargs)

    def list_images(self) -> list:
        return self._page.get_images(full=True)

    def render_to_ppm(self, scale: float = 1.0, colorspace: str = "rgb") -> bytes:
        matrix = fitz.Matrix(scale, scale)
        pix    = self._page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=False)
        return pix.tobytes("ppm")

    def render_to_png_bytes(self, scale: float = 1.0) -> bytes:
        matrix = fitz.Matrix(scale, scale)
        pix    = self._page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB, alpha=True)
        return pix.tobytes("png")

    def get_image_info(self) -> list:
        return self._page.get_image_info(xrefs=True)

    def get_text_dict(self) -> dict:
        return self._page.get_text("dict")

    def get_text_blocks(self) -> list[tuple]:
        return self._page.get_text("blocks")

    def get_text_rawdict(self) -> dict:
        return self._page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    def get_links(self) -> list[dict]:
        return self._page.get_links()

    def search_text(self, query: str) -> list[fitz.Rect]:
        return self._page.search_for(query)

    def add_highlight(self, quads: fitz.Quad | fitz.Rect) -> fitz.Annot:
        return self._page.add_highlight_annot(quads)

    def add_rect_annotation(
        self,
        rect: tuple[float, float, float, float],
        color: tuple[float, float, float] = (1, 0, 0),
        fill: tuple[float, float, float] | None = None,
        width: float = 1.5,
    ) -> fitz.Annot:
        rect_obj = fitz.Rect(*rect)
        annot    = self._page.add_rect_annot(rect_obj)
        annot.set_border(width=width)
        annot.set_colors(stroke=color, fill=fill)
        annot.update()
        return annot

    def get_annotations(self) -> list[fitz.Annot]:
        return list(self._page.annots())

    def delete_annotation(self, annot: fitz.Annot) -> None:
        self._page.delete_annot(annot)

    def crop(self, rect: tuple[float, float, float, float]) -> None:
        self._page.set_cropbox(fitz.Rect(*rect))

    def add_redact_annot(
        self,
        rect: tuple[float, float, float, float],
        fill_color: tuple[float, float, float] | None = (0.0, 0.0, 0.0),
        replacement_text: str = "",
    ) -> None:
        fitz_rect = fitz.Rect(*rect)
        self._page.add_redact_annot(
            quad=fitz_rect,
            fill=list(fill_color) if fill_color is not None else None,
            text=replacement_text if replacement_text else None,
            fontsize=10 if replacement_text else 0,
        )

    def apply_redactions(self) -> None:
        try:
            self._page.apply_redactions(
                images=_REDACT_IMAGE_PIXELS,
                graphics=_REDACT_LINE_ART_IF_COVERED,
            )
        except TypeError:
            self._page.apply_redactions()

    def search_text_quads(
        self,
        query: str,
        case_sensitive: bool = False,
    ) -> list[tuple[float, float, float, float]]:
        flags = 0 if case_sensitive else getattr(fitz, "TEXT_DEHYPHENATE", 0)
        quads = self._page.search_for(query, quads=True, flags=flags)
        return [tuple(q.rect) for q in quads]