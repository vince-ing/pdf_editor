"""
Tooltip — lightweight hover tooltip for any Tk widget.
"""

import tkinter as tk
from src.gui.theme import PALETTE


class Tooltip:
    def __init__(self, widget: tk.Widget, text: str):
        self._tip = None
        widget.bind("<Enter>", lambda e: self._show(e, text))
        widget.bind("<Leave>", self._hide)

    def _show(self, event, text: str):
        x = event.widget.winfo_rootx() + 20
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 4
        self._tip = tw = tk.Toplevel()
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw, text=text,
            bg="#1C1C26", fg="#E8E8F0",
            font=("Helvetica", 9), relief="flat",
            padx=8, pady=4,
            bd=1, highlightbackground="#2A2A3D",
            highlightthickness=1,
        ).pack()

    def _hide(self, _e=None):
        if self._tip:
            self._tip.destroy()
            self._tip = None