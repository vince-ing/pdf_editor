"""
TtsService — offline text-to-speech via kokoro-onnx 0.5.x.

kokoro-onnx >= 0.4.0 requires explicit model paths.
This service downloads the model files once to a local cache folder
(pdf_editor/models/kokoro/) and reuses them on every subsequent run.

Install: pip install kokoro-onnx soundfile sounddevice
"""

from __future__ import annotations

import os
import re 
import time
import threading
import urllib.request
from typing import Callable

# Model files hosted by the kokoro-onnx project on Hugging Face
_MODEL_URL  = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

# Cache next to the project root so it survives venv rebuilds
_HERE        = os.path.dirname(os.path.abspath(__file__))          # src/services/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))            # pdf_editor/
_CACHE_DIR   = os.path.join(_PROJECT_ROOT, "models", "kokoro")
_MODEL_PATH  = os.path.join(_CACHE_DIR, "kokoro-v1.0.onnx")
_VOICES_PATH = os.path.join(_CACHE_DIR, "voices-v1.0.bin")


def _download(url: str, dest: str, label: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[TTS] Downloading {label}…")
    urllib.request.urlretrieve(url, dest)
    print(f"[TTS] Saved to {dest}")


class TtsService:
    """
    Wraps kokoro-onnx 0.5.x for offline TTS playback on a background thread.

    Parameters
    ----------
    on_start : callable, optional
        Called on the worker thread when speech starts.
    on_stop : callable, optional
        Called on the worker thread when speech ends naturally.
    on_error : callable(str), optional
        Called with an error message if something goes wrong.
    """

    def __init__(
        self,
        on_start: Callable | None = None,
        on_playback_start: Callable | None = None,
        on_progress: Callable[[int, int, int], None] | None = None,
        on_stop:  Callable | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        self._on_start          = on_start
        self._on_playback_start = on_playback_start
        self._on_progress       = on_progress
        self._on_stop           = on_stop
        self._on_error          = on_error

        self._kokoro    = None
        self._stop_evt  = threading.Event()
        self._pause_evt = threading.Event()
        self._pause_evt.set()
        self._thread: threading.Thread | None = None
        self._speaking  = False

        # Voice options: 'af_heart', 'af_sky', 'am_adam', 'bf_emma', 'bm_george'
        self.voice = "af_alloy"
        self.speed = 1.0

    # ── public API ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Speak text. Stops any current speech first. Non-blocking."""
        self.stop()
        text = text.strip()
        if not text:
            return
        self._stop_evt.clear()
        self._pause_evt.set()
        self._thread = threading.Thread(
            target=self._worker, args=(text,), daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        self._pause_evt.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        self._speaking = False

    def pause(self) -> None:
        self._pause_evt.clear()

    def resume(self) -> None:
        self._pause_evt.set()

    def toggle_pause(self) -> None:
        if self._pause_evt.is_set():
            self.pause()
        else:
            self.resume()

    @property
    def is_speaking(self) -> bool:
        return self._speaking

    @property
    def is_paused(self) -> bool:
        return not self._pause_evt.is_set()

    # ── internals ─────────────────────────────────────────────────────────────

    def _ensure_models(self) -> None:
        """Download model files if not already cached."""
        if not os.path.exists(_MODEL_PATH):
            _download(_MODEL_URL, _MODEL_PATH, "Kokoro model (~80 MB)")
        if not os.path.exists(_VOICES_PATH):
            _download(_VOICES_URL, _VOICES_PATH, "Kokoro voices (~10 MB)")

    def _load_kokoro(self):
        if self._kokoro is not None:
            return self._kokoro
        try:
            from kokoro_onnx import Kokoro
        except ImportError:
            raise RuntimeError(
                "kokoro-onnx not installed. Run:\n"
                "pip install kokoro-onnx soundfile sounddevice"
            )
        self._ensure_models()
        self._kokoro = Kokoro(_MODEL_PATH, _VOICES_PATH)
        return self._kokoro

    def _worker(self, text: str) -> None:
        """Background thread: chunk text, generate audio, track ETA, then play it."""
        self._speaking = True
        if self._on_start:
            self._on_start()

        try:
            import sounddevice as sd
            import numpy as np

            print("[TTS] Loading kokoro...")
            kokoro = self._load_kokoro()
            print("[TTS] Generating audio...")

            # 1. Chunk text roughly by sentences to provide progress
            # Use regex to split by punctuation followed by space
            chunks = [c.strip() for c in re.split(r'(?<=[.!?])\s+', text) if c.strip()]
            if not chunks:
                chunks = [text]

            total_chars = sum(len(c) for c in chunks)
            processed_chars = 0
            
            all_samples = []
            sample_rate = 24000 # default fallback
            
            start_time = time.time()

            # 2. Iteratively process chunks and calculate ETA
            for chunk in chunks:
                if self._stop_evt.is_set():
                    print("[TTS] Stopped before playback")
                    return

                samples, sr = kokoro.create(
                    chunk,
                    voice=self.voice,
                    speed=self.speed,
                    lang="en-us",
                )
                
                if hasattr(samples, 'tolist'):
                    all_samples.extend(samples.tolist())
                else:
                    all_samples.extend(samples)
                sample_rate = sr

                processed_chars += len(chunk)
                elapsed = time.time() - start_time
                chars_per_sec = processed_chars / elapsed if elapsed > 0 else 0
                remaining_chars = total_chars - processed_chars
                eta = int(remaining_chars / chars_per_sec) if chars_per_sec > 0 else 0

                if self._on_progress:
                    self._on_progress(processed_chars, total_chars, eta)

            if self._stop_evt.is_set():
                print("[TTS] Stopped before playback")
                return

            self._pause_evt.wait()
            if self._stop_evt.is_set():
                return
                
            if self._on_playback_start:
                self._on_playback_start()

            # 3. Play complete audio
            samples_arr = np.array(all_samples, dtype=np.float32)
            print(f"[TTS] Playing {len(samples_arr)/sample_rate:.1f}s of audio...")

            sd.play(samples_arr, samplerate=sample_rate)
            sd.wait()  # Simple blocking wait — most reliable
            print("[TTS] Playback complete")

        except Exception as exc:
            import traceback
            print("[TTS] ERROR:", exc)
            traceback.print_exc()
            if self._on_error:
                self._on_error(str(exc))
        finally:
            self._speaking = False
            if self._on_stop and not self._stop_evt.is_set():
                self._on_stop()