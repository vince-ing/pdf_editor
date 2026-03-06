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
        # foreground must be set explicitly on every tag — on Windows, applying
        # a tag overrides the widget-level fg with the tag's own foreground,
        # which defaults to the system colour (often invisible on some themes).
        self.tag_configure("normal",      font=self._font_normal,      foreground=color_hex)
        self.tag_configure("bold",        font=self._font_bold,        foreground=color_hex)
        self.tag_configure("italic",      font=self._font_italic,      foreground=color_hex)
        self.tag_configure("bold_italic", font=self._font_bold_italic, foreground=color_hex)

        self.canvas             = canvas
        self.pdf_bbox           = pdf_bbox
        self.on_commit_callback = on_commit
        self._committed         = False

        # ── Insert rich text span-by-span ────────────────────────────────
        self._insert_rich_text(rich_text)

        self.bind("<FocusOut>", self._commit)
        self.bind("<Escape>",   self._cancel)
        self.bind("<Control-b>", self._toggle_bold)
        self.bind("<Control-i>", self._toggle_italic)
        # Re-apply the active insertion tag after every keypress so that
        # characters typed inside or adjacent to a styled run keep their style.
        self.bind("<Key>",       self._on_key)
        self._active_tag: str = "normal"   # tracks what style new chars get

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
    # Tag toggling  (Ctrl+B / Ctrl+I)
    # ------------------------------------------------------------------

    def _toggle_tag(self, tag: str) -> None:
        """
        Toggle *tag* on the current selection.  If the entire selection already
        carries the tag, remove it; otherwise apply it to the whole selection.
        Also updates ``_active_tag`` so that subsequent typed characters inherit
        the correct style automatically.
        """
        try:
            sel_start = self.index("sel.first")
            sel_end   = self.index("sel.last")
            has_selection = True
        except tk.TclError:
            has_selection = False

        if has_selection:
            # Check whether the tag already covers the whole selection
            ranges = self.tag_ranges(tag)
            # Build a set of absolute offsets covered by this tag
            lines = self.get("1.0", "end-1c").split("\n")
            covered = set()
            for i in range(0, len(ranges), 2):
                s = self._tk_index_to_abs(str(ranges[i]),     lines)
                e = self._tk_index_to_abs(str(ranges[i + 1]), lines)
                covered.update(range(s, e))
            s_abs = self._tk_index_to_abs(sel_start, lines)
            e_abs = self._tk_index_to_abs(sel_end,   lines)
            sel_range = set(range(s_abs, e_abs))
            fully_tagged = sel_range and sel_range.issubset(covered)

            if fully_tagged:
                self.tag_remove(tag, sel_start, sel_end)
            else:
                self.tag_add(tag, sel_start, sel_end)
        else:
            # No selection — toggle the insertion-point style for future typing
            pass

        # Update active tag to match what's at the insertion cursor
        self._active_tag = self._tag_at_insert()

    def _toggle_bold(self, event=None) -> str:
        self._toggle_tag("bold")
        return "break"   # prevent Tkinter default Ctrl+B behaviour

    def _toggle_italic(self, event=None) -> str:
        self._toggle_tag("italic")
        return "break"

    def _tag_at_insert(self) -> str:
        """Return the style tag that should apply at the current insert cursor."""
        idx   = self.index("insert")
        lines = self.get("1.0", "end-1c").split("\n")
        abs_i = self._tk_index_to_abs(idx, lines)
        if abs_i > 0:
            # Look at the character just before the cursor (the one most recently typed)
            check_abs = abs_i - 1
        else:
            check_abs = 0

        total = len("".join(lines))  # rough upper bound
        bold   = False
        italic = False
        for tag_name, flag in [("bold", True), ("italic", True)]:
            ranges = self.tag_ranges(tag_name)
            for i in range(0, len(ranges), 2):
                s = self._tk_index_to_abs(str(ranges[i]),     lines)
                e = self._tk_index_to_abs(str(ranges[i + 1]), lines)
                if s <= check_abs < e:
                    if tag_name == "bold":
                        bold = True
                    else:
                        italic = True
                    break

        if bold and italic: return "bold_italic"
        if bold:            return "bold"
        if italic:          return "italic"
        return "normal"

    def _on_key(self, event=None) -> None:
        """
        After a printable key is pressed, ensure the character just inserted
        carries the correct style tag.

        Tkinter inserts new characters with no tag by default.  We immediately
        look back one position from the cursor and apply ``_active_tag`` to
        that single character if it currently has no style tag.
        """
        if event and (event.keysym in ("BackSpace", "Delete", "Return",
                                        "Left", "Right", "Up", "Down",
                                        "Home", "End", "Prior", "Next") or
                      event.state & 0x4):   # Ctrl-key combos
            # Navigation / deletion — re-evaluate what tag is now active
            self._active_tag = self._tag_at_insert()
            return

        # Schedule the tag application after Tkinter has finished inserting
        # the character (the insert happens between keydown and our handler)
        self.after(0, self._apply_active_tag_to_last_char)

    def _apply_active_tag_to_last_char(self) -> None:
        """Apply _active_tag to the character immediately before the cursor."""
        if self._active_tag == "normal":
            return
        try:
            cursor = self.index("insert")
            prev   = self.index("insert - 1 chars")
            # Only tag it if it has no style tag yet
            existing = [t for t in self.tag_names(prev)
                        if t in ("bold", "italic", "bold_italic")]
            if not existing:
                self.tag_add(self._active_tag, prev, cursor)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Rich-text insertion
    # ------------------------------------------------------------------

    def _insert_rich_text(self, rich_text: list) -> None:
        """
        Insert all text first as plain, then apply style tags explicitly.

        Tkinter's tag gravity means inserting text immediately after a tagged
        region (at its right boundary) extends the tag to cover the new text.
        To prevent this, we insert ALL content untagged in one pass, then use
        tag_add() to apply styles by exact character position. This completely
        avoids the boundary-extension problem.
        """
        # ── Pass 1: insert all text plain (no tags) ───────────────────────
        plain_lines = []
        for spans in rich_text:
            plain_lines.append("".join(t for t, _ in spans))
        self.insert("1.0", "\n".join(plain_lines))

        # ── Pass 2: apply style tags by exact position ────────────────────
        abs_offset = 0
        lines = plain_lines
        for line_idx, spans in enumerate(rich_text):
            for chunk_text, chunk_flags in spans:
                if not chunk_text:
                    continue
                tag = _tag_name(chunk_flags)
                start_abs = abs_offset
                end_abs   = abs_offset + len(chunk_text)
                if tag != "normal":
                    start_idx = self._abs_to_tk_index(start_abs, lines)
                    end_idx   = self._abs_to_tk_index(end_abs,   lines)
                    self.tag_add(tag, start_idx, end_idx)
                abs_offset += len(chunk_text)
            abs_offset += 1  # newline between lines

    @staticmethod
    def _abs_to_tk_index(abs_offset: int, lines: list) -> str:
        """Convert an absolute character offset to a Tkinter line.col index."""
        remaining = abs_offset
        for line_num, line in enumerate(lines):
            line_len = len(line) + 1  # +1 for newline
            if remaining <= len(line):
                return f"{line_num + 1}.{remaining}"
            remaining -= line_len
        # Clamp to end of last line
        return f"{len(lines)}.{len(lines[-1]) if lines else 0}"

    # ------------------------------------------------------------------
    # Rich-text extraction
    # ------------------------------------------------------------------

    def _extract_rich_text(self) -> list:
        """
        Reconstruct a RichText structure from the widget's current content.

        Queries the flags for each character using tag_names() called at the
        MIDDLE of each character's range ("line.col" to "line.col+1"), which
        avoids the boundary ambiguity of point queries. This is safe now that
        _insert_rich_text no longer uses tag gravity (all tags are applied via
        explicit tag_add calls, so there is no bleed-over at boundaries).
        """
        raw        = self.get("1.0", "end-1c")
        lines_text = raw.split("\n")

        style_tag_flags = {
            "bold":        _FLAG_BOLD,
            "italic":      _FLAG_ITALIC,
            "bold_italic": _FLAG_BOLD | _FLAG_ITALIC,
        }

        result: list[list[tuple[str, int]]] = []

        for line_idx, line_str in enumerate(lines_text):
            tk_line = line_idx + 1
            spans: list[tuple[str, int]] = []

            if line_str:
                current_flags = self._flags_at(tk_line, 0, style_tag_flags)
                current_buf   = [line_str[0]]

                for col in range(1, len(line_str)):
                    f = self._flags_at(tk_line, col, style_tag_flags)
                    if f == current_flags:
                        current_buf.append(line_str[col])
                    else:
                        spans.append(("".join(current_buf), current_flags))
                        current_flags = f
                        current_buf   = [line_str[col]]

                spans.append(("".join(current_buf), current_flags))

            result.append(spans if spans else [("", 0)])

        return result

    def _flags_at(self, tk_line: int, col: int, tag_flag_map: dict) -> int:
        """
        Return the combined style flags for the character at (tk_line, col).
        Queries tag_names over the range col -> col+1 so Tkinter reports tags
        that genuinely cover the character, not just its left boundary.
        """
        start = f"{tk_line}.{col}"
        end   = f"{tk_line}.{col + 1}"
        tags  = self.tag_names(start)   # tags active at this position
        flags = 0
        for tag, flag in tag_flag_map.items():
            if tag in tags:
                flags |= flag
        return flags

    @staticmethod
    def _tk_index_to_abs(tk_index: str, lines: list) -> int:
        """
        Convert a Tkinter ``"line.col"`` index string to an absolute
        character offset into the text joined by ``\n``.
        Tkinter line numbers are 1-based; col numbers are 0-based.
        """
        line_s, col_s = tk_index.split(".")
        line = int(line_s) - 1
        col  = int(col_s)
        offset = sum(len(lines[i]) + 1 for i in range(min(line, len(lines))))
        return offset + col

    # ------------------------------------------------------------------
    # Commit / cancel
    # ------------------------------------------------------------------

    def _commit(self, event=None):
        if self._committed:
            return
        self._committed = True
        rich = self._extract_rich_text()
        print("\n=== COMMIT DEBUG ===")
        for i, line in enumerate(rich):
            print(f"  line {i}: {line}")
        print("=== END COMMIT DEBUG ===\n")
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