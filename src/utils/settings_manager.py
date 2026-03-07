# src/utils/settings_manager.py
import os
import json
from pathlib import Path

class SettingsManager:
    """Centralizes persistence for tool styles, recent files, and window geometry."""
    def __init__(self, app_name="PDFEditor"):
        self.app_name = app_name
        self.config_dir = os.path.join(str(Path.home()), f".{app_name.lower()}")
        self.config_path = os.path.join(self.config_dir, "config.json")
        
        self.settings = {
            "recent_files": [],
            "window_geometry": "1280x860+0+0",
            "window_maximized": False,
            "tool_styles": {
                "annot_stroke_rgb":  (92, 138, 110),
                "annot_fill_rgb":    None,
                "annot_width":       1.5,
                "draw_mode":         "pen",
                "draw_stroke_rgb":   (92, 138, 110),
                "draw_fill_rgb":     None,
                "draw_width":        2.0,
                "draw_opacity":      1.0,
                "font_index":        0,
                "fontsize":          14,
                "text_color":        (0, 0, 0),
                "text_align":        0,
                "redact_fill_color": (0.0, 0.0, 0.0),
                "redact_label":      "",
            }
        }
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.config_path): return
        try:
            with open(self.config_path, "r") as f:
                data = json.load(f)
                if "tool_styles" in data:
                    self.settings["tool_styles"].update(data["tool_styles"])
                    # Convert JSON lists back to RGB tuples
                    ts = self.settings["tool_styles"]
                    for k in ["annot_stroke_rgb", "annot_fill_rgb", "draw_stroke_rgb", "draw_fill_rgb", "text_color", "redact_fill_color"]:
                        if k in ts and isinstance(ts[k], list): ts[k] = tuple(ts[k])
                if "recent_files" in data: self.settings["recent_files"] = data["recent_files"]
                if "window_geometry" in data: self.settings["window_geometry"] = data["window_geometry"]
                if "window_maximized" in data: self.settings["window_maximized"] = data["window_maximized"]
        except Exception: pass

    def save(self) -> None:
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_path, "w") as f:
                json.dump(self.settings, f, indent=4)
        except Exception: pass

    def get(self, key, default=None): return self.settings.get(key, default)
    def set(self, key, value): self.settings[key] = value

    # Recent Files Access
    def get_recent_files(self) -> list[str]: return self.settings["recent_files"]
    def clear_recent_files(self) -> None: self.settings["recent_files"] = []
    
    def add_recent_file(self, path: str) -> None:
        recents = self.settings["recent_files"]
        if path in recents: recents.remove(path)
        recents.insert(0, path)
        self.settings["recent_files"] = recents[:10]