import tkinter as tk
import tkinter.font as tkFont


def _resolve_tk_family(pdf_font_name: str) -> str:
    """
    Map a PDF font name to a real Tkinter/system font family name.
    """
    lower = pdf_font_name.lower()

    checks = [
        ("courier new",     "Courier New"),
        ("couriernew",      "Courier New"),
        ("cour",            "Courier New"),
        ("consolas",        "Consolas"),
        ("consolasmt",      "Consolas"),
        ("times new roman", "Times New Roman"),
        ("timesnewroman",   "Times New Roman"),
        ("timesmt",         "Times New Roman"),
        ("times",           "Times New Roman"),
        ("tiro",            "Times New Roman"),
        ("georgia",         "Georgia"),
        ("arial",           "Arial"),
        ("helv",            "Arial"),
        ("helvetica",       "Arial"),
        ("calibri",         "Calibri"),
        ("cambria",         "Cambria"),
        ("verdana",         "Verdana"),
        ("trebuchet",       "Trebuchet MS"),
        ("garamond",        "Garamond"),
        ("symbol",          "Symbol"),
        ("wingdings",       "Wingdings"),
        ("zadb",            "Wingdings"),
        ("zapf",            "Wingdings"),
    ]

    for fragment, family in checks:
        if fragment in lower:
            return family

    return "Arial"


def _is_bold(flags: int) -> bool:
    """PyMuPDF span flags bit 4 (0x10) = bold."""
    return bool(flags & (1 << 4))


def _is_italic(flags: int) -> bool:
    """PyMuPDF span flags bit 1 (0x02) = italic."""
    return bool(flags & (1 << 1))


def _tag_name(flags: int) -> str:
    """Return the canonical Tkinter tag name for a given flags value."""
    bold   = _is_bold(flags)
    italic = _is_italic(flags)
    if bold and italic:
        return "bold_italic"
    if bold:
        return "bold"
    if italic:
        return "italic"
    return "normal"


# ---------------------------------------------------------------------------
# Flags constants — mirror the PyMuPDF bit layout used by EditTextCommand.
# ---------------------------------------------------------------------------
_FLAG_BOLD   = 1 << 4   # 16
_FLAG_ITALIC = 1 << 1   # 2


class EditOverlay(tk.Text):
    """
    A borderless text widget that overlays the PDF canvas for in-place editing.

    Rich text is accepted as a ``RichText`` value (same type alias as in
    ``EditTextCommand``):

        list[list[tuple[str, int]]]   — lines → spans → (text, flags)

    Tkinter ``tags`` are configured for ``normal``, ``bold``, ``italic``, and
    ``bold_italic``.  On commit the tag ranges are walked to reconstruct the
    same structure so the writer knows which chunks need which font.
    """

    def __init__(
        self,
        canvas,
        pdf_bbox,
        rich_text,          # RichText — list[list[tuple[str, int]]]
        font_family,
        font_size,
        color_hex,
        scale_factor,
        ox,
        oy,
        on_commit,
        baseline_y=None,
        page_width=None,
        line_spacing=1.2,
    ):
        tk_family = _resolve_tk_family(font_family)
        pixel_size = -max(8, round(font_size * scale_factor))

        # ── Base (normal) font ────────────────────────────────────────────
        self._font_normal = tkFont.Font(
            family=tk_family, size=pixel_size,
            weight="normal", slant="roman",
        )
        self._font_bold = tkFont.Font(
            family=tk_family, size=pixel_size,
            weight="bold", slant="roman",
        )
        self._font_italic = tkFont.Font(
            family=tk_family, size=pixel_size,
            weight="normal", slant="italic",
        )
        self._font_bold_italic = tkFont.Font(
            family=tk_family, size=pixel_size,
            weight="bold", slant="italic",
        )

        # Line-spacing: extra inter-line pixels to match the PDF layout
        tk_linespace          = self._font_normal.metrics("linespace")
        target_linespace_px   = line_spacing * font_size * scale_factor
        extra_spacing         = max(0, int(round(target_linespace_px - tk_linespace)))

        super().__init__(
            canvas,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=self._font_normal,   # default; overridden per-span via tags
            fg=color_hex,
            bg="#ffffff",
            wrap="word",
            undo=True,
            spacing1=0,
            spacing2=extra_spacing,
            spacing3=extra_spacing,
        )

        # ── Configure style tags ─────────────────────────────────────────
        # Each tag only overrides the font; colour stays the widget default.
        self.tag_configure("normal",      font=self._font_normal)
        self.tag_configure("bold",        font=self._font_bold)
        self.tag_configure("italic",      font=self._font_italic)
        self.tag_configure("bold_italic", font=self._font_bold_italic)

        self.canvas             = canvas
        self.pdf_bbox           = pdf_bbox
        self.on_commit_callback = on_commit
        self._committed         = False

        # ── Insert rich text span-by-span ────────────────────────────────
        self._insert_rich_text(rich_text)

        self.bind("<FocusOut>", self._commit)
        self.bind("<Escape>",   self._cancel)

        # ── Geometry ─────────────────────────────────────────────────────
        x0, y0, x1, y1 = pdf_bbox

        if page_width is not None:
            calc_width = max((x1 - x0) * 1.05, page_width - (2 * x0))
            width = calc_width * scale_factor
        else:
            width = (x1 - x0) * 1.05 * scale_factor

        height = ((y1 - y0) * scale_factor) + 8
        x_pos  = x0 * scale_factor + ox

        if baseline_y is not None:
            ascent_px         = self._font_normal.metrics("ascent")
            baseline_canvas_y = baseline_y * scale_factor + oy
            y_pos             = baseline_canvas_y - ascent_px
        else:
            y_pos = y0 * scale_factor + oy

        self.window_id = self.canvas.create_window(
            x_pos, y_pos,
            window=self,
            anchor="nw",
            width=width + 6,
            height=max(25, height + 6),
        )

        self.focus_set()

    # ------------------------------------------------------------------
    # Rich-text insertion
    # ------------------------------------------------------------------

    def _insert_rich_text(self, rich_text: list) -> None:
        """
        Insert all lines and spans into the Text widget, tagging each chunk
        so its visual style matches the source PDF span.
        """
        for line_idx, spans in enumerate(rich_text):
            if line_idx > 0:
                # Insert the newline with the tag of the last span on the
                # previous line so the cursor style is sensible there.
                self.insert(tk.END, "\n")

            for chunk_text, chunk_flags in spans:
                if not chunk_text:
                    continue
                tag = _tag_name(chunk_flags)
                self.insert(tk.END, chunk_text, tag)

    # ------------------------------------------------------------------
    # Rich-text extraction
    # ------------------------------------------------------------------

    def _extract_rich_text(self) -> list:
        """
        Walk the widget's content character-by-character and reconstruct a
        ``RichText`` structure that mirrors what ``EditTextCommand`` expects.

        Strategy
        --------
        1.  Get the full plain text (split on ``\\n`` to recover lines).
        2.  For each character position, determine which style tag applies and
            merge consecutive same-flag characters into a single span.
        3.  Return ``list[list[tuple[str, int]]]``.
        """
        # Map tag names back to flag integers
        tag_to_flags: dict[str, int] = {
            "normal":      0,
            "bold":        _FLAG_BOLD,
            "italic":      _FLAG_ITALIC,
            "bold_italic": _FLAG_BOLD | _FLAG_ITALIC,
        }
        style_tags = set(tag_to_flags.keys())

        raw = self.get("1.0", "end-1c")   # full text, no trailing newline
        lines_text = raw.split("\n")

        result: list[list[tuple[str, int]]] = []

        # We walk Tkinter indices: "line.col" — both 1-based for line, 0-based for col
        for line_idx, line_str in enumerate(lines_text):
            tk_line = line_idx + 1          # Tkinter lines are 1-based
            spans: list[tuple[str, int]] = []
            current_flags: int | None = None
            current_buf: list[str]    = []

            for col_idx in range(len(line_str)):
                tk_index = f"{tk_line}.{col_idx}"

                # Find which style tags are active at this character
                active_style_tags = [
                    t for t in self.tag_names(tk_index)
                    if t in style_tags
                ]

                # Resolve to a single flags value — prefer most specific
                if "bold_italic" in active_style_tags:
                    flags = tag_to_flags["bold_italic"]
                elif "bold" in active_style_tags:
                    flags = tag_to_flags["bold"]
                elif "italic" in active_style_tags:
                    flags = tag_to_flags["italic"]
                else:
                    flags = 0

                if flags == current_flags:
                    current_buf.append(line_str[col_idx])
                else:
                    # Flush the previous run
                    if current_buf and current_flags is not None:
                        spans.append(("".join(current_buf), current_flags))
                    current_flags = flags
                    current_buf   = [line_str[col_idx]]

            # Flush the final run on this line
            if current_buf and current_flags is not None:
                spans.append(("".join(current_buf), current_flags))

            # Always emit a line entry, even if it's empty
            result.append(spans if spans else [("", 0)])

        return result

    # ------------------------------------------------------------------
    # Commit / cancel
    # ------------------------------------------------------------------

    def _commit(self, event=None):
        if self._committed:
            return
        self._committed = True
        rich = self._extract_rich_text()
        self.destroy_overlay()
        self.on_commit_callback(rich, self.pdf_bbox)

    def _cancel(self, event=None):
        self._committed = True
        self.destroy_overlay()

    def destroy_overlay(self):
        try:
            self.canvas.delete(self.window_id)
            self.destroy()
        except Exception:
            pass