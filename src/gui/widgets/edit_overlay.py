import tkinter as tk
import tkinter.font as tkFont


def _resolve_tk_family(pdf_font_name: str) -> str:
    """
    Map a PDF font name to a real Tkinter/system font family name.

    PDF fonts come back as e.g. "ArialMT", "Arial-BoldMT", "Arial,Bold",
    "TimesNewRomanPSMT", "CourierNewPSMT" — exact-match dicts miss all of
    these.  We do a case-insensitive substring search instead.
    """
    lower = pdf_font_name.lower()

    # Order matters: more specific patterns first
    checks = [
        ("courier new",     "Courier New"),
        ("couriernew",      "Courier New"),
        ("cour",            "Courier New"),
        ("consolas",        "Consolas"),
        ("consolasmt",      "Consolas"),
        ("times new roman", "Times New Roman"),
        ("timesnewroman",   "Times New Roman"),
        ("timesmt",         "Times New Roman"),
        ("tiro",            "Times New Roman"),
        ("georgia",         "Georgia"),
        ("arial",           "Arial"),          # catches ArialMT, Arial-BoldMT, etc.
        ("helv",            "Arial"),          # PostScript alias
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

    # Unknown font — fall back to Arial rather than passing the raw PDF name,
    # which Tkinter won't recognise and will silently substitute anyway.
    return "Arial"


def _is_bold(flags: int) -> bool:
    """PyMuPDF span flags bit 4 (0x10) = bold."""
    return bool(flags & (1 << 4))


def _is_italic(flags: int) -> bool:
    """PyMuPDF span flags bit 1 (0x02) = italic."""
    return bool(flags & (1 << 1))


class EditOverlay(tk.Text):
    """
    A borderless text widget that overlays the PDF canvas for in-place editing.
    """

    def __init__(
        self,
        canvas,
        pdf_bbox,
        text,
        font_family,
        font_size,
        color_hex,
        scale_factor,
        ox,
        oy,
        on_commit,
        baseline_y=None,
        font_flags=0,
    ):
        tk_family = _resolve_tk_family(font_family)

        # Bold / italic from PDF span flags
        weight = "bold"   if _is_bold(font_flags)   else "normal"
        slant  = "italic" if _is_italic(font_flags) else "roman"

        # Negative size = absolute pixel height, bypasses OS DPI scaling
        pixel_size = -max(8, round(font_size * scale_factor))

        # Build the font object now so we can measure ascent before placing
        self._tk_font = tkFont.Font(
            family=tk_family,
            size=pixel_size,
            weight=weight,
            slant=slant,
        )

        super().__init__(
            canvas,
            bd=0,
            highlightthickness=0,
            padx=0,
            pady=0,
            font=self._tk_font,
            fg=color_hex,
            bg="#ffffff",
            wrap="word",
            undo=True,
            spacing1=0,
            spacing2=0,
            spacing3=0,
        )

        self.canvas              = canvas
        self.pdf_bbox            = pdf_bbox
        self.on_commit_callback  = on_commit
        self._committed          = False

        self.insert("1.0", text)
        self.bind("<FocusOut>", self._commit)
        self.bind("<Escape>",   self._cancel)

        x0, y0, x1, y1 = pdf_bbox
        width  = (x1 - x0) * scale_factor
        height = (y1 - y0) * scale_factor
        x_pos  = x0 * scale_factor + ox

        # ── Precise vertical alignment ─────────────────────────────────────
        # tk.Text (with pady=0, spacing1=0) draws the first line so that its
        # BASELINE sits at widget_top + font_ascent.
        # We want the baseline to land on the PDF baseline, so:
        #   widget_top = pdf_baseline_canvas_y - font_ascent
        if baseline_y is not None:
            ascent_px          = self._tk_font.metrics("ascent")
            baseline_canvas_y  = baseline_y * scale_factor + oy
            y_pos              = baseline_canvas_y - ascent_px
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

    # ── commit / cancel ───────────────────────────────────────────────────────

    def _commit(self, event=None):
        if self._committed:
            return
        self._committed = True
        new_text = self.get("1.0", "end-1c").strip()
        self.destroy_overlay()                        # destroy BEFORE render fires
        self.on_commit_callback(new_text, self.pdf_bbox)

    def _cancel(self, event=None):
        self._committed = True
        self.destroy_overlay()

    def destroy_overlay(self):
        try:
            self.canvas.delete(self.window_id)
            self.destroy()
        except Exception:
            pass