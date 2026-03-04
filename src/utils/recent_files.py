"""
RecentFiles — persists a most-recently-used list of PDF paths to disk.

Storage location (created automatically if absent):
  Windows  : %APPDATA%\\PDFEditor\\recent.json
  macOS    : ~/Library/Application Support/PDFEditor/recent.json
  Linux    : ~/.config/PDFEditor/recent.json

Up to MAX_ENTRIES paths are stored.  Paths that no longer exist on disk
are silently dropped when the list is read back.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys


MAX_ENTRIES = 10


def _config_dir() -> pathlib.Path:
    if sys.platform == "win32":
        base = pathlib.Path(os.environ.get("APPDATA", "~")).expanduser()
    elif sys.platform == "darwin":
        base = pathlib.Path("~/Library/Application Support").expanduser()
    else:
        base = pathlib.Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return base / "PDFEditor"


def _json_path() -> pathlib.Path:
    return _config_dir() / "recent.json"


class RecentFiles:
    """Thread-safe-enough MRU list backed by a JSON file."""

    def __init__(self):
        self._path = _json_path()

    # ── public API ────────────────────────────────────────────────────────────

    def get(self) -> list[str]:
        """Return stored paths that still exist on disk, newest first."""
        raw = self._load()
        return [p for p in raw if pathlib.Path(p).is_file()]

    def add(self, filepath: str) -> None:
        """Prepend filepath to the list, deduplicating and trimming to MAX_ENTRIES."""
        # Normalise so the same file opened via different relative paths matches
        norm = str(pathlib.Path(filepath).resolve())
        raw  = self._load()
        # Remove any existing entry for this file (case-insensitive on Windows)
        if sys.platform == "win32":
            raw = [p for p in raw if p.lower() != norm.lower()]
        else:
            raw = [p for p in raw if p != norm]
        raw.insert(0, norm)
        self._save(raw[:MAX_ENTRIES])

    def remove(self, filepath: str) -> None:
        """Remove a specific path (e.g. if the file was deleted externally)."""
        norm = str(pathlib.Path(filepath).resolve())
        raw  = self._load()
        if sys.platform == "win32":
            raw = [p for p in raw if p.lower() != norm.lower()]
        else:
            raw = [p for p in raw if p != norm]
        self._save(raw)

    def clear(self) -> None:
        self._save([])

    # ── internals ─────────────────────────────────────────────────────────────

    def _load(self) -> list[str]:
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                return [str(p) for p in data if isinstance(p, str)]
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return []

    def _save(self, entries: list[str]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        except OSError:
            pass  # Non-fatal — app works fine without persistence