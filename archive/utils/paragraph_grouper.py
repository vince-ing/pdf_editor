"""
paragraph_grouper.py
────────────────────
Re-groups raw PyMuPDF spans into logical paragraphs by baseline proximity,
bypassing PyMuPDF's built-in block heuristics which are unreliable for
documents with irregular line spacing.

Usage
-----
    from src.utils.paragraph_grouper import group_page_spans, paragraph_bbox, paragraph_line_spacing

    # page is a fitz.Page
    paragraphs = group_page_spans(page)          # list[list[span_dict]]
    for para in paragraphs:
        bbox    = paragraph_bbox(para)           # (x0, y0, x1, y1) in PDF points
        spacing = paragraph_line_spacing(para)   # float, e.g. 1.25

Data model
----------
Each ``span_dict`` is the span dict from ``page.get_text("dict")``:
  - "text"      str
  - "origin"    (x, y) — the baseline insertion point
  - "bbox"      (x0, y0, x1, y1)
  - "size"      float — font size in points
  - "flags"     int   — bold/italic bits (same as PyMuPDF)
  - "font"      str
  - "color"     int   — packed sRGB
  - "ascender"  float — relative ascender (×size = pt above baseline)
  - "descender" float — relative descender (negative, ×size = pt below baseline)

A ``paragraph`` is a list[span_dict] whose spans all come from consecutive
lines of the same logical text block.  Spans that differ in font size, are
in a different column, or are separated by a gap larger than
``BASELINE_GAP_MULTIPLIER × font_size`` are placed in a new paragraph.
"""

from __future__ import annotations

# ──────────────────────────────────────────────────────────────────────────────
# Tunable thresholds
# ──────────────────────────────────────────────────────────────────────────────

# A baseline gap greater than this multiple of font_size starts a new paragraph.
# 2.0× catches even loose 1.8× leading while still splitting on genuine gaps.
BASELINE_GAP_MULTIPLIER: float = 2.0

# Spans whose left edges differ by more than this fraction of page_width are in
# different columns and must not be merged.
X_PROXIMITY_FRACTION: float = 0.35

# Minimum absolute x-distance (points) that always triggers a column split,
# regardless of page_width.  Prevents 0-width pages from disabling the check.
X_PROXIMITY_MIN_PT: float = 60.0

# Whitespace-only spans are skipped during grouping (they carry no useful
# content but can produce spurious baseline readings in some PDFs).
_WHITESPACE = frozenset(" \t\r\n\xa0")


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def group_page_spans(page) -> list[list[dict]]:
    """
    Return all logical paragraphs on *page* as a list of span-lists.

    Parameters
    ----------
    page : fitz.Page
        An open PyMuPDF page object.

    Returns
    -------
    list[list[dict]]
        Each inner list is one paragraph; each dict is a raw PyMuPDF span.
        Paragraphs are in top-to-bottom, left-to-right reading order.
    """
    raw       = page.get_text_dict()
    page_w    = page.width

    # Flatten all text spans from every block, preserving document order.
    # get_text("dict") spans carry "text" directly. "rawdict" puts chars in
    # span["chars"] not span["text"], so get_text_dict() is correct here.
    # We intentionally ignore PyMuPDF's block grouping and re-derive it.
    all_spans: list[dict] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:          # skip image blocks
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = span.get("text", "")
                if not text or all(c in _WHITESPACE for c in text):
                    continue
                all_spans.append(span)

    if not all_spans:
        return []

    # Sort spans by baseline y so paragraphs are in top-to-bottom order.
    # For spans on the same baseline (same visual line), preserve their original
    # document order from PyMuPDF rather than sorting by x — PyMuPDF already
    # returns spans left-to-right within a line, and re-sorting by x would
    # place wrapped continuation lines (x=72) before inline labels (x=125).
    all_spans.sort(key=lambda s: round(s["origin"][1], 1))

    return _cluster(all_spans, page_w)


def paragraph_bbox(para: list[dict]) -> tuple[float, float, float, float]:
    """
    Return the tight bounding box that encloses all spans in the paragraph.

    Returns
    -------
    tuple[float, float, float, float]
        (x0, y0, x1, y1) in PDF points.
    """
    x0 = min(s["bbox"][0] for s in para)
    y0 = min(s["bbox"][1] for s in para)
    x1 = max(s["bbox"][2] for s in para)
    y1 = max(s["bbox"][3] for s in para)
    return (x0, y0, x1, y1)


def paragraph_line_spacing(para: list[dict]) -> float:
    """
    Compute the average baseline-to-baseline line spacing ratio for a paragraph.

    Returns a float in the range [0.8, 2.5] that can be passed directly as
    the ``lineheight`` argument to ``EditTextCommand``.
    """
    if len(para) < 2:
        # Single-line paragraph: estimate from bbox height
        h     = para[0]["bbox"][3] - para[0]["bbox"][1]
        size  = para[0]["size"] or 12.0
        ratio = h / size
        return max(0.8, min(2.5, ratio))

    gaps: list[float] = []
    for i in range(1, len(para)):
        prev_baseline = para[i - 1]["origin"][1]
        curr_baseline = para[i]["origin"][1]
        prev_size     = para[i - 1]["size"] or 12.0
        gap           = curr_baseline - prev_baseline
        if gap > 0:                          # skip negative gaps (shouldn't happen post-sort)
            gaps.append(gap / prev_size)

    if not gaps:
        return 1.2

    ratio = sum(gaps) / len(gaps)
    return max(0.8, min(2.5, ratio))


def hit_test(pdf_x: float, pdf_y: float, para: list[dict], margin: float = 4.0) -> bool:
    """
    Return True if the PDF-space point *(pdf_x, pdf_y)* falls within or near
    the paragraph's bounding box.

    Parameters
    ----------
    margin : float
        Extra points added on all four sides for forgiving click targeting.
    """
    x0, y0, x1, y1 = paragraph_bbox(para)
    return (
        (x0 - margin) <= pdf_x <= (x1 + margin)
        and (y0 - margin) <= pdf_y <= (y1 + margin)
    )


# ──────────────────────────────────────────────────────────────────────────────
# Internal clustering
# ──────────────────────────────────────────────────────────────────────────────

def _spans_are_same_paragraph(
    prev: dict,
    curr: dict,
    para_x0: float,
    page_width: float,
) -> bool:
    """
    Return True if *curr* should be appended to the same paragraph as *prev*.

    Rules (any failure → new paragraph):
    1.  Font size changed by more than 0.5pt.
    2.  Baseline moved strictly upward (new column / text frame).
    3.  Baseline gap exceeds ``BASELINE_GAP_MULTIPLIER × prev_font_size``.
    4.  When baselines differ, curr's x is far from the paragraph's leftmost x
        (para_x0), indicating a different column.  We compare against para_x0
        rather than prev's x because edited lines may end mid-page — comparing
        the last span's x to the next line's left-margin x would falsely trigger
        a column split every time a line contains multiple styled spans.
    """
    prev_size     = prev["size"]
    curr_size     = curr["size"]
    prev_baseline = prev["origin"][1]
    curr_baseline = curr["origin"][1]
    curr_x0       = curr["bbox"][0]

    # Rule 1 — font size changed
    if abs(prev_size - curr_size) > 0.5:
        return False

    # Rule 2 — baseline moved strictly upward
    if curr_baseline < prev_baseline - 0.5:
        return False

    # Rule 3 — gap too large (only when baseline actually advanced)
    gap = curr_baseline - prev_baseline
    if gap > 0:
        limit = (prev_size or 12.0) * BASELINE_GAP_MULTIPLIER
        if gap > limit:
            return False

    # Rule 4 — different column (only when baseline advanced, i.e. a real new line).
    # Compare curr's x to para_x0 (the leftmost x in the whole paragraph so far)
    # so that line-wraps back to the left margin are never mistaken for columns.
    if curr_baseline > prev_baseline + 0.5:
        x_threshold = max(X_PROXIMITY_MIN_PT, page_width * X_PROXIMITY_FRACTION)
        if abs(curr_x0 - para_x0) > x_threshold:
            return False

    return True


def _cluster(spans: list[dict], page_width: float) -> list[list[dict]]:
    """Group a sorted flat span list into paragraphs."""
    paragraphs: list[list[dict]] = []
    current: list[dict] = [spans[0]]
    para_x0: float = spans[0]["bbox"][0]   # leftmost x seen in current paragraph

    for span in spans[1:]:
        if _spans_are_same_paragraph(current[-1], span, para_x0, page_width):
            current.append(span)
            para_x0 = min(para_x0, span["bbox"][0])
        else:
            paragraphs.append(current)
            current = [span]
            para_x0 = span["bbox"][0]

    paragraphs.append(current)
    return paragraphs