# src/gui/controllers/window_controller.py
from __future__ import annotations
import tkinter as tk

from src.gui.components.icon_toolbar import TOOL_KEY_MAP
from src.gui.theme import PALETTE

class WindowController:
    """Handles OS window chrome (minimize/maximize/close) and global key bindings."""
    def __init__(self, root: tk.Tk, callbacks: dict):
        self.root = root
        self.cb = callbacks
        self._maximized = False
        self._pre_max_geometry = "1280x860+0+0"
        self._min_helper = None

        self._bind_keys()
        self.root.protocol("WM_DELETE_WINDOW", self.cb["on_closing"])

    def _bind_keys(self) -> None:
        r = self.root
        b = self.cb
        r.bind("<Control-o>", lambda e: b["open"]())
        r.bind("<Control-s>", lambda e: b["save"]())
        r.bind("<Control-S>", lambda e: b["save_as"]())
        r.bind("<Control-z>", lambda e: b["undo"]())
        r.bind("<Control-y>", lambda e: b["redo"]())
        r.bind("<Control-equal>", lambda e: b["zoom_in"]())
        r.bind("<Control-minus>", lambda e: b["zoom_out"]())
        r.bind("<Control-0>", lambda e: b["zoom_reset"]())
        r.bind("<Control-1>", lambda e: b["zoom_fit_width"]())
        r.bind("<Control-2>", lambda e: b["zoom_fit_page"]())
        r.bind("<Left>", lambda e: b["prev_page"]())
        r.bind("<Right>", lambda e: b["next_page"]())
        r.bind("<Escape>", lambda e: b["on_escape"]())
        r.bind("<Control-c>", lambda e: b["copy"]())
        r.bind("<Control-f>", lambda e: b["toggle_search"]())
        r.bind("<F3>", lambda e: b["search_next"]())
        r.bind("<Shift-F3>", lambda e: b["search_prev"]())
        r.bind("<Control-t>", lambda e: b["toggle_inspector"]())
        r.bind("<KeyPress>", self._on_key_press)

    def _on_key_press(self, event: tk.Event) -> None:
        if isinstance(self.root.focus_get(), (tk.Entry, tk.Text)): return
        key = event.keysym.lower()
        if key in TOOL_KEY_MAP:
            self.cb["select_tool"](TOOL_KEY_MAP[key])
            self.cb["flash_status"](
                f"Tool: {TOOL_KEY_MAP[key].replace('_', ' ').title()}  [{key.upper()}]",
                color=PALETTE["accent_light"], duration_ms=1200
            )

    def minimize(self) -> None:
        self.root.withdraw()
        self._min_helper = tk.Toplevel(self.root)
        self._min_helper.title("PDF Editor")
        self._min_helper.geometry("1x1+-10000+-10000")
        self._min_helper.iconify()
        self._min_helper.protocol("WM_DELETE_WINDOW", self.restore)
        self._min_helper.bind("<Map>", lambda e: self.restore())

    def restore(self) -> None:
        if self._min_helper:
            try: self._min_helper.destroy()
            except Exception: pass
            self._min_helper = None
        self.root.deiconify()

    def maximize(self) -> None:
        if self._maximized:
            self.root.geometry(self._pre_max_geometry)
            self._maximized = False
        else:
            self._pre_max_geometry = self.root.geometry()
            try:
                import ctypes
                class RECT(ctypes.Structure):
                    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
                r = RECT()
                ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
                w, h, x, y = r.right - r.left, r.bottom - r.top, r.left, r.top
            except Exception:
                w, h, x, y = self.root.winfo_screenwidth(), self.root.winfo_screenheight(), 0, 0
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            self._maximized = True
            
    def close(self) -> None:
        self.cb["on_closing"]()