from __future__ import annotations

import fitz

# ── version-safe redaction constants ─────────────────────────────────────────
_REDACT_IMAGE_PIXELS        = getattr(fitz, "PDF_REDACT_IMAGE_PIXELS",        2)
_REDACT_LINE_ART_IF_COVERED = getattr(fitz, "PDF_REDACT_LINE_ART_IF_COVERED", 1)


class PDFPage:
    """
    Core wrapper for PyMuPDF (fitz) Page.
    Handles operations specific to a single page.
    """

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
        """Rotates the page by the specified angle (must be a multiple of 90)."""
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
        rect: tuple[float, float, float, float],
        text: str,
        fontsize: int = 12,
        fontname: str = "helv",
        color: tuple[float, float, float] = (0, 0, 0),
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

    def insert_image(
        self,
        rect_coords: tuple[float, float, float, float],
        image_path: str | None = None,
        stream: bytes | None = None,
    ) -> None:
        """Inserts an image into the defined rectangle boundary."""
        rect = fitz.Rect(*rect_coords)
        kwargs: dict = {}
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

    def get_text_dict(self) -> dict:
        """
        Return the full page text as a nested dict with blocks, lines, and spans.
        Used for true in-place text editing to extract exact font properties and bboxes.
        """
        return self._page.get_text("dict")

    def get_text_blocks(self) -> list[tuple]:
        """Returns text blocks as (x0, y0, x1, y1, text, block_no, block_type)."""
        return self._page.get_text("blocks")

    def get_text_rawdict(self) -> dict:
        """
        Return the full page text as a nested dict with per-character bboxes.

        Structure: {"blocks": [{"type": 0, "lines": [{"spans": [{"chars":
            [{"c": str, "bbox": (x0,y0,x1,y1), "origin": (x,y)}, ...]}]}]}]}

        type 0 = text block, type 1 = image block.
        Used by SelectTextTool for character-level hit detection.
        """
        return self._page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    def get_links(self) -> list[dict]:
        return self._page.get_links()

    def search_text(self, query: str) -> list[fitz.Rect]:
        """Returns a list of fitz.Rect instances where the query text is found."""
        return self._page.search_for(query)

    def add_highlight(self, quads: fitz.Quad | fitz.Rect) -> fitz.Annot:
        """Adds a highlight annotation over the given quads/rects."""
        return self._page.add_highlight_annot(quads)

    def add_rect_annotation(
        self,
        rect: tuple[float, float, float, float],
        color: tuple[float, float, float] = (1, 0, 0),
        fill: tuple[float, float, float] | None = None,
        width: float = 1.5,
    ) -> fitz.Annot:
        rect_obj = fitz.Rect(*rect)
        annot = self._page.add_rect_annot(rect_obj)
        annot.set_border(width=width)
        annot.set_colors(stroke=color, fill=fill)
        annot.update()
        return annot

    def get_annotations(self) -> list[fitz.Annot]:
        return list(self._page.annots())

    def delete_annotation(self, annot: fitz.Annot) -> None:
        self._page.delete_annot(annot)

    def crop(self, rect: tuple[float, float, float, float]) -> None:
        """Crops the page's visible area to the given rect."""
        self._page.set_cropbox(fitz.Rect(*rect))

    # ── redaction ─────────────────────────────────────────────────────────────

    def add_redact_annot(
        self,
        rect: tuple[float, float, float, float],
        fill_color: tuple[float, float, float] | None = (0.0, 0.0, 0.0),
        replacement_text: str = "",
    ) -> None:
        """
        Mark *rect* as a redaction annotation without applying it yet.

        Call ``apply_redactions()`` after marking all desired rects so that
        apply_redactions() runs exactly once per redaction operation. Calling
        apply_redactions() after each individual mark corrupts multi-match
        redactions because subsequent annotations are applied to a stale page.

        Parameters
        ----------
        rect : tuple
            (x0, y0, x1, y1) in PDF user-space points.
        fill_color : tuple
            RGB 0.0–1.0 fill for the burnt-in box. Defaults to black.
        replacement_text : str
            Optional label drawn on the redaction box. Empty string = no label.
        """
        fitz_rect = fitz.Rect(*rect)
        self._page.add_redact_annot(
            quad=fitz_rect,
            fill=list(fill_color) if fill_color is not None else None,
            text=replacement_text if replacement_text else None,
            fontsize=10 if replacement_text else 0,
        )

    def apply_redactions(self) -> None:
        """
        Permanently burn in all pending redaction annotations on this page.

        This destroys the underlying text, images, and vector graphics — it is
        irreversible. Always call this after all ``add_redact_annot()`` calls
        for a given operation are complete, never in a per-rect loop.
        """
        try:
            self._page.apply_redactions(
                images=_REDACT_IMAGE_PIXELS,
                graphics=_REDACT_LINE_ART_IF_COVERED,
            )
        except TypeError:
            # PyMuPDF < 1.21 — apply_redactions() takes no keyword arguments
            self._page.apply_redactions()

    def search_text_quads(
        self,
        query: str,
        case_sensitive: bool = False,
    ) -> list[tuple[float, float, float, float]]:
        """
        Search for *query* and return bounding rects for every hit.

        Returns
        -------
        list of (x0, y0, x1, y1) tuples in PDF user-space points.
        """
        flags = 0 if case_sensitive else getattr(fitz, "TEXT_DEHYPHENATE", 0)
        quads = self._page.search_for(query, quads=True, flags=flags)
        return [tuple(q.rect) for q in quads]