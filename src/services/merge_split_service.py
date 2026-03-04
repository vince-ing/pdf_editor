"""
MergeSplitService — combines multiple PDFs into one, or splits a single PDF
into separate files.

All fitz operations are self-contained here so commands stay thin wrappers.
"""

from __future__ import annotations
import fitz
from src.core.document import PDFDocument


class MergeSplitService:
    """Business logic for merging and splitting PDF documents."""

    # ── merge ─────────────────────────────────────────────────────────────────

    def merge_pdfs(self, input_paths: list[str], output_path: str) -> int:
        """
        Concatenate all PDFs in *input_paths* into a single file at *output_path*.

        Returns the total page count of the merged document.
        Raises on any I/O or PDF error.
        """
        if not input_paths:
            raise ValueError("No input files provided.")

        out = fitz.open()
        try:
            for path in input_paths:
                src = fitz.open(path)
                try:
                    out.insert_pdf(src)
                finally:
                    src.close()
            out.save(output_path, garbage=4, deflate=True)
            return len(out)
        finally:
            out.close()

    # ── split ─────────────────────────────────────────────────────────────────

    def split_pdf_by_range(
        self,
        document: PDFDocument,
        page_ranges: list[tuple[int, int]],
        output_paths: list[str],
    ) -> list[int]:
        """
        Extract page ranges from *document* into separate files.

        Parameters
        ----------
        document : PDFDocument
            The open source document.
        page_ranges : list of (first, last) inclusive 0-based index pairs.
        output_paths : list of output file paths, same length as page_ranges.

        Returns a list of page counts for each output file.
        """
        if len(page_ranges) != len(output_paths):
            raise ValueError("page_ranges and output_paths must have the same length.")

        counts = []
        for (first, last), out_path in zip(page_ranges, output_paths):
            out = fitz.open()
            try:
                out.insert_pdf(document._doc, from_page=first, to_page=last)
                out.save(out_path, garbage=4, deflate=True)
                counts.append(len(out))
            finally:
                out.close()
        return counts

    def split_pdf_every_n(
        self,
        document: PDFDocument,
        n: int,
        output_dir: str,
        base_name: str = "part",
    ) -> list[str]:
        """
        Split *document* into chunks of *n* pages each.

        Files are written as ``<output_dir>/<base_name>_001.pdf``, etc.
        Returns the list of output paths created.
        """
        import os, math
        if n < 1:
            raise ValueError("n must be >= 1.")
        total     = document.page_count
        num_parts = math.ceil(total / n)
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        for i in range(num_parts):
            first = i * n
            last  = min(first + n - 1, total - 1)
            part_num = str(i + 1).zfill(len(str(num_parts)))
            out_path = os.path.join(output_dir, f"{base_name}_{part_num}.pdf")
            out = fitz.open()
            try:
                out.insert_pdf(document._doc, from_page=first, to_page=last)
                out.save(out_path, garbage=4, deflate=True)
            finally:
                out.close()
            paths.append(out_path)
        return paths

    def split_pdf_single_pages(
        self,
        document: PDFDocument,
        output_dir: str,
        base_name: str = "page",
    ) -> list[str]:
        """
        Extract every page of *document* as its own PDF file.

        Returns the list of output paths created.
        """
        import os
        total = document.page_count
        os.makedirs(output_dir, exist_ok=True)
        paths = []
        pad = len(str(total))
        for i in range(total):
            out_path = os.path.join(output_dir, f"{base_name}_{str(i + 1).zfill(pad)}.pdf")
            out = fitz.open()
            try:
                out.insert_pdf(document._doc, from_page=i, to_page=i)
                out.save(out_path, garbage=4, deflate=True)
            finally:
                out.close()
            paths.append(out_path)
        return paths