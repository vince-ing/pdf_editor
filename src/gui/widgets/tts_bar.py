"""
TtsBar — slim playback control bar that slides in above the status bar.

Mirrors the FindBar pattern exactly: owned by main_window, shown/hidden
via show() / hide(), pure presentation with no business logic.

Layout:
  ✕  |  🔊 Reading page 2…  |  ⏸ Pause  |  ◼ Stop  |  Speed: [0.5──●──2.0]
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
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
        Called when the user clicks ◼ Stop or ✕.  The caller is responsible
        for stopping the TTS engine *and* hiding this bar.
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

        self._playback_frame: tk.Frame
        self._loading_frame: tk.Frame
        self._progress: ttk.Progressbar
        self._eta_lbl: tk.Label

        self._build()

    # ── public API ────────────────────────────────────────────────────────────

    def show(self, status: str = "Reading…") -> None:
        """Show the bar."""
        if not self._visible:
            self._bar.pack(side=tk.BOTTOM, fill=tk.X)
            self._visible = True
        self.set_status(status)
        self.show_playback_controls()
        self.set_paused(False)

    def hide(self) -> None:
        """Hide the bar (safe to call even when already hidden)."""
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

    def show_loading(self) -> None:
        self._playback_frame.pack_forget()
        self._loading_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._progress.config(value=0)
        self._eta_lbl.config(text="Generating…")

    def update_progress(self, done: int, total: int, pct: int) -> None:
        """Update the loading bar. done/total are sentence counts, pct is 0-100."""
        self._progress.config(maximum=total, value=done)
        if done >= total:
            self._eta_lbl.config(text="Starting…")
        else:
            self._eta_lbl.config(text=f"{pct}%  ({done}/{total})")

    def show_playback_controls(self) -> None:
        self._loading_frame.pack_forget()
        self._playback_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        bar = self._bar

        def _btn(parent_frame, text, cmd, fg=PALETTE["fg_primary"], bg=PALETTE["bg_hover"]):
            return tk.Button(
                parent_frame, text=text, command=cmd,
                bg=bg, fg=fg,
                activebackground=PALETTE["accent_dim"],
                activeforeground=PALETTE["accent_light"],
                font=FONT_LABEL, relief="flat", bd=0,
                padx=10, pady=2, cursor="hand2", highlightthickness=0,
            )

        def _sep(parent_frame):
            tk.Frame(parent_frame, bg=PALETTE["border"], width=1).pack(
                side=tk.LEFT, fill=tk.Y, pady=6, padx=4)

        # ── Leftmost fixed section: Close (✕) + Status ────────────────────────
        # The ✕ button is a *dismiss* button: it calls on_stop, which is
        # responsible for stopping the engine AND hiding the bar.
        fixed_frame = tk.Frame(bar, bg=PALETTE["bg_mid"])
        fixed_frame.pack(side=tk.LEFT, fill=tk.Y)

        _btn(fixed_frame, "✕", self._on_stop,
             fg=PALETTE["fg_dim"], bg=PALETTE["bg_mid"]).pack(side=tk.LEFT)
        _sep(fixed_frame)

        self._status_lbl = tk.Label(
            fixed_frame, text="Reading…",
            bg=PALETTE["bg_mid"], fg=PALETTE["accent_light"],
            font=FONT_MONO, padx=8, anchor="w",
        )
        self._status_lbl.pack(side=tk.LEFT)
        _sep(fixed_frame)

        # ── Loading frame (shown while audio is being generated) ──────────────
        self._loading_frame = tk.Frame(bar, bg=PALETTE["bg_mid"])
        self._progress = ttk.Progressbar(
            self._loading_frame, orient="horizontal",
            length=150, mode="determinate")
        self._progress.pack(side=tk.LEFT, padx=(4, 8), fill=tk.Y, pady=8)

        self._eta_lbl = tk.Label(
            self._loading_frame, text="ETA: --s",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"], font=FONT_LABEL,
        )
        self._eta_lbl.pack(side=tk.LEFT, padx=(0, 8))

        # ── Playback frame (shown during playback) ────────────────────────────
        self._playback_frame = tk.Frame(bar, bg=PALETTE["bg_mid"])

        self._pause_btn = _btn(
            self._playback_frame, "⏸ Pause", self._on_pause_resume)
        self._pause_btn.pack(side=tk.LEFT, padx=(0, 4))

        # ◼ Stop — stops the engine AND hides the bar (same as ✕)
        _btn(self._playback_frame, "◼ Stop", self._on_stop,
             fg="#FFCCCC", bg="#7B2020").pack(side=tk.LEFT, padx=(0, 4))
        _sep(self._playback_frame)

        tk.Label(
            self._playback_frame, text="Speed:",
            bg=PALETTE["bg_mid"], fg=PALETTE["fg_dim"], font=FONT_LABEL,
        ).pack(side=tk.LEFT, padx=(4, 2))

        tk.Scale(
            self._playback_frame,
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
        ).pack(side=tk.LEFT, padx=(0, 8))

        # Default to showing playback controls
        self.show_playback_controls()