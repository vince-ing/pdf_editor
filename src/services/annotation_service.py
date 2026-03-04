"""
AnnotationService — business logic for highlight, rectangle, and draw annotations.

All fitz-level drawing logic lives here so GUI tool classes stay free of
PyMuPDF imports and direct document access.
"""

from __future__ import annotations

import fitz

from src.core.document import PDFDocument


class AnnotationService:
    """Handles adding and removing annotations on PDF pages."""

    # ── highlight / rect ──────────────────────────────────────────────────────

    def add_highlight(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
    ) -> None:
        """
        Adds a yellow highlight annotation over the given rect.

        Parameters
        ----------
        rect : tuple
            (x0, y0, x1, y1) in PDF user-space points.
        """
        page = document.get_page(page_index)
        quad = fitz.Rect(*rect).quad
        page.add_highlight(quad)

    def add_rect_annotation(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple,
        color: tuple = (1, 0, 0),
        fill: tuple | None = None,
        width: float = 1.5,
    ) -> None:
        """
        Draws a rectangle annotation on the page.

        Parameters
        ----------
        color : tuple
            RGB 0.0–1.0 stroke colour.
        fill : tuple | None
            RGB 0.0–1.0 fill colour, or None for transparent.
        width : float
            Stroke width in points.
        """
        page = document.get_page(page_index)
        page.add_rect_annotation(rect, color=color, fill=fill, width=width)

    # ── draw-tool annotations ─────────────────────────────────────────────────

    def add_ink_annotation(
        self,
        document: PDFDocument,
        page_index: int,
        pdf_points: list[tuple[float, float]],
        stroke: tuple[float, float, float] = (0.0, 0.0, 0.0),
        width: float = 2.0,
        opacity: float = 1.0,
    ) -> int:
        """
        Write a freehand ink (pen) annotation to the PDF.

        Parameters
        ----------
        pdf_points : list of (x, y) tuples in PDF user-space points.
        stroke : RGB 0.0–1.0 stroke colour.
        width : Stroke width in points.
        opacity : 0.0–1.0 opacity.

        Returns
        -------
        int
            The xref of the newly created annotation (used by DrawAnnotationCommand
            for undo).
        """
        fitz_page = document.get_page(page_index)._page
        ink_list  = [[(float(x), float(y)) for x, y in pdf_points]]
        annot     = fitz_page.add_ink_annot(ink_list)
        annot.set_colors(stroke=stroke)
        annot.set_border(width=width)
        annot.set_opacity(opacity)
        annot.update()
        return annot.xref

    def add_line_annotation(
        self,
        document: PDFDocument,
        page_index: int,
        p1: tuple[float, float],
        p2: tuple[float, float],
        stroke: tuple[float, float, float] = (0.0, 0.0, 0.0),
        width: float = 2.0,
        opacity: float = 1.0,
        arrow: bool = False,
    ) -> int:
        """
        Write a straight line (or arrow) annotation to the PDF.

        Parameters
        ----------
        p1, p2 : (x, y) tuples in PDF user-space points.
        arrow : If True, add an open-arrow end cap at p2.

        Returns
        -------
        int
            The xref of the newly created annotation.
        """
        fitz_page = document.get_page(page_index)._page
        annot     = fitz_page.add_line_annot(p1, p2)
        annot.set_colors(stroke=stroke)
        annot.set_border(width=width)
        annot.set_opacity(opacity)
        if arrow:
            annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)
        annot.update()
        return annot.xref

    def add_circle_annotation(
        self,
        document: PDFDocument,
        page_index: int,
        rect: tuple[float, float, float, float],
        stroke: tuple[float, float, float] = (0.0, 0.0, 0.0),
        fill: tuple[float, float, float] | None = None,
        width: float = 2.0,
        opacity: float = 1.0,
    ) -> int:
        """
        Write an ellipse/circle annotation to the PDF.

        Parameters
        ----------
        rect : (x0, y0, x1, y1) bounding box in PDF user-space points.
        fill : RGB 0.0–1.0 fill colour, or None for transparent interior.

        Returns
        -------
        int
            The xref of the newly created annotation.
        """
        fitz_page = document.get_page(page_index)._page
        annot     = fitz_page.add_circle_annot(rect)
        colors    = {"stroke": stroke}
        if fill is not None:
            colors["fill"] = fill
        annot.set_colors(**colors)
        annot.set_border(width=width)
        annot.set_opacity(opacity)
        annot.update()
        return annot.xref