"""
TtsBar — slim playback control bar that slides in above the status bar.

Mirrors the FindBar pattern exactly: owned by main_window, shown/hidden
via show() / hide(), pure presentation with no business logic.

Layout:
  ✕  |  🔊 Reading page 2…  |  ⏸ Pause  |  ◼ Stop  |  Speed: [0.5──●──2.0]
"""

from __future__ import annotations

import tkinter as tk
from src.gui.theme import PALETTE, FONT_LABEL, FONT_MONO


class TtsBar:
    """
    Compact TTS playback bar packed at the bottom of the root window,
    between the canvas area and the status bar.

    Parameters
    ----------
    parent : tk.Widget
        The root window.
    on_stop : callable
        Called when the user clicks ◼ Stop or ✕.
    on_pause_resume : callable
        Called when the user clicks ⏸ / ▶.
    on_speed_change : callable(float)
        Called when the speed slider moves; receives the new speed value.
    """

    def __init__(
        self,
        parent: tk.Widget,
        on_stop:         callable,
        on_pause_resume: callable,
        on_speed_change: callable,
    ) -> None:
        self._on_stop         = on_stop
        self._on_pause_resume = on_pause_resume
        self._on_speed_change = on_speed_change
        self._visible         = False

        self._bar = tk.Frame(
            parent,
            bg=PALETTE["bg_mid"],
            height=36,
            highlightthickness=1,
            highlightbackground=PALETTE["border"],
        )
        self._bar.pack_propagate(False)

        self._speed_var = tk.DoubleVar(value=1.0)
        self._pause_btn: tk.Button
        self._status_lbl: tk.Label

        self._build()

    # ── public API ────────────────────────────────────────────────────────────

    def show(self, status: str = "Reading…") -> None:
        """Slide the bar in."""
        if not self._visible:
            self._bar.pack(side=tk.BOTTOM, fill=tk.X)
            self._visible = True
        self.set_status(status)
        self.set_paused(False)

    def hide(self) -> None:
        """Slide the bar out."""
        if self._visible:
            self._bar.pack_forget()
            self._visible = False

    @property
    def is_visible(self) -> bool:
        return self._visible

    def set_status(self, text: str) -> None:
        self._status_lbl.config(text=text)

    def set_paused(self, paused: bool) -> None:
        self._pause_btn.config(text="▶ Resume" if paused else "⏸ Pause")

    def get_speed(self) -> float:
        return round(self._speed_var.get(), 2)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        bar = self._bar

        def _btn(text, cmd, fg=PALETTE["fg_primary"], bg=PALETTE["bg_hover"]):
            return tk.Button(
                bar, text=text, command=cmd,
                bg=bg, fg=fg,
                activebackground=PALETTE["accent_dim"],
                activeforeground=PALETTE["accent_light"],
                font=FONT_LABEL, relief="flat", bd=0,
                padx=10, pady=2, cursor="hand2", highlightthickness=0,
            )

        def _sep():
            tk.Frame(bar, bg=PALETTE["border"], width=1).pack(
                side=tk.LEFT, fill=tk.Y, pady=6, padx=4)

        # Close / stop (leftmost)
        _btn("✕", self._on_stop,
             fg=PALETTE["fg_dim"],
             bg=PALETTE["bg_mid"]).pack(side=tk.LEFT)

        _sep()

        # Status label
        self._status_lbl = tk.Label(
            bar, text="Reading…",
            bg=PALETTE["bg_mid"], fg=PALETTE["accent_light"],
            font=FONT_MONO, padx=8, anchor="w",
        )
        self._status_lbl.pack(side=tk.LEFT)

        _sep()

        # Pause / Resume
        self._pause_btn = _btn("⏸ Pause", self._on_pause_resume)
        self._pause_btn.pack(side=tk.LEFT, padx=(0, 4))

        # Stop
        _btn("◼ Stop", self._on_stop,
             fg="#FFCCCC", bg="#7B2020").pack(side=tk.LEFT, padx=(0, 4))

        _sep()

        # Speed label + slider (right side)
        tk.Label(
            bar, text="Speed:",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"],
            font=FONT_LABEL,
        ).pack(side=tk.LEFT, padx=(4, 2))

        speed_slider = tk.Scale(
            bar,
            variable=self._speed_var,
            from_=0.5, to=2.0, resolution=0.1,
            orient=tk.HORIZONTAL, length=100,
            command=lambda v: self._on_speed_change(float(v)),
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_primary"],
            troughcolor=PALETTE["bg_hover"],
            activebackground=PALETTE["accent"],
            highlightthickness=0, bd=0,
            sliderrelief="flat", showvalue=True,
            font=("Helvetica Neue", 7),
        )
        speed_slider.pack(side=tk.LEFT, padx=(0, 8))