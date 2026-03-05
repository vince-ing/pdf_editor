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
_HERE         = os.path.dirname(os.path.abspath(__file__))   # src/services/
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))      # pdf_editor/
_CACHE_DIR    = os.path.join(_PROJECT_ROOT, "models", "kokoro")
_MODEL_PATH   = os.path.join(_CACHE_DIR, "kokoro-v1.0.onnx")
_VOICES_PATH  = os.path.join(_CACHE_DIR, "voices-v1.0.bin")

# How many audio frames to write per callback tick (controls pause/stop latency).
# At 24 kHz, 2048 frames ≈ 85 ms — responsive without too many callbacks.
_CHUNK_FRAMES = 2048


def _download(url: str, dest: str, label: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[TTS] Downloading {label}…")
    urllib.request.urlretrieve(url, dest)
    print(f"[TTS] Saved to {dest}")


class TtsService:
    """
    Wraps kokoro-onnx 0.5.x for offline TTS playback on a background thread.

    Playback is done via a sounddevice OutputStream with a manual chunk loop
    so that stop and pause events are honoured within ~85 ms.

    Parameters
    ----------
    on_start : callable, optional
        Called on the worker thread when generation begins.
    on_playback_start : callable, optional
        Called on the worker thread just before audio starts playing.
    on_progress : callable(int, int, int), optional
        Called with (processed_chars, total_chars, eta_seconds) during generation.
    on_stop : callable, optional
        Called on the worker thread when speech ends *naturally* (not user stop).
    on_error : callable(str), optional
        Called with an error message if something goes wrong.
    """

    def __init__(
        self,
        on_start:          Callable | None = None,
        on_playback_start: Callable | None = None,
        on_progress:       Callable[[int, int, int], None] | None = None,
        on_stop:           Callable | None = None,
        on_error:          Callable[[str], None] | None = None,
    ) -> None:
        self._on_start          = on_start
        self._on_playback_start = on_playback_start
        self._on_progress       = on_progress
        self._on_stop           = on_stop
        self._on_error          = on_error

        self._kokoro    = None
        self._stop_evt  = threading.Event()
        self._pause_evt = threading.Event()
        self._pause_evt.set()   # not paused initially
        self._thread: threading.Thread | None = None
        self._speaking  = False

        # Voice options: 'af_heart', 'af_sky', 'am_adam', 'bf_emma', 'bm_george'
        self.voice = "af_alloy"
        self.speed = 1.0

    # ── public API ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Start speaking *text*. Stops any current speech first. Non-blocking."""
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
        """Stop playback immediately. The audio position is *not* remembered."""
        self._stop_evt.set()
        self._pause_evt.set()   # unblock a paused thread so it can exit
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

    def _play_samples(self, samples, sample_rate: int) -> bool:
        """
        Stream *samples* (numpy float32 array) through an OutputStream,
        checking stop/pause every _CHUNK_FRAMES output frames.

        Speed is read from self.speed on every iteration so the slider
        takes effect within ~85 ms without pausing or restarting.

        Strategy: each iteration we consume (chunk_frames * speed) source
        frames, resample them down to chunk_frames output frames via linear
        interpolation, then write those to the stream.  Faster speed →
        more source frames consumed per tick → audio finishes sooner.
        Pitch is not preserved (it rises slightly at higher speeds) which
        is acceptable for speech and avoids a heavy DSP dependency.

        Returns True if playback completed normally, False if interrupted.
        """
        import sounddevice as sd
        import numpy as np

        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples.reshape(-1, 1)

        n_channels = samples.shape[1]
        total      = len(samples)
        # Use a float position so fractional-frame accumulation is exact.
        pos_f: float = 0.0

        with sd.OutputStream(samplerate=sample_rate,
                             channels=n_channels,
                             dtype="float32") as stream:
            while pos_f < total:
                # ── stop ────────────────────────────────────────────────────
                if self._stop_evt.is_set():
                    stream.abort()
                    return False

                # ── pause ────────────────────────────────────────────────────
                if not self._pause_evt.is_set():
                    stream.stop()
                    self._pause_evt.wait()
                    if self._stop_evt.is_set():
                        return False
                    stream.start()

                # ── read current speed and compute source window ──────────────
                speed = max(0.1, float(self.speed))   # guard against 0 / negative
                # How many source frames we want to consume this tick
                src_frames = int(_CHUNK_FRAMES * speed)
                src_start  = int(pos_f)
                src_end    = min(src_start + src_frames, total)
                src_chunk  = samples[src_start:src_end]

                if len(src_chunk) == 0:
                    break

                # ── resample src_chunk → _CHUNK_FRAMES output frames ──────────
                src_len = len(src_chunk)
                if src_len == _CHUNK_FRAMES:
                    # Speed is exactly 1.0 (or chunk lands perfectly) — no work needed
                    out_chunk = src_chunk
                else:
                    # Linear interpolation along the time axis for each channel
                    out_indices = np.linspace(0, src_len - 1, _CHUNK_FRAMES)
                    lo  = np.floor(out_indices).astype(np.int32)
                    hi  = np.minimum(lo + 1, src_len - 1)
                    frac = (out_indices - lo)[:, np.newaxis]   # (frames, 1) broadcast
                    out_chunk = src_chunk[lo] * (1.0 - frac) + src_chunk[hi] * frac

                stream.write(out_chunk.astype(np.float32))
                pos_f += src_frames   # advance by how many source frames we consumed

        return True

    def _worker(self, text: str) -> None:
        """
        Background thread:
          1. Generate all audio chunks (with progress callbacks).
          2. Play the complete buffer through the interruptible stream loop.
        """
        self._speaking = True
        if self._on_start:
            self._on_start()

        naturally_stopped = False

        try:
            import numpy as np

            print("[TTS] Loading kokoro...")
            kokoro = self._load_kokoro()
            print("[TTS] Generating audio...")

            # ── 1. Generation phase ──────────────────────────────────────────
            chunks = [c.strip() for c in re.split(r'(?<=[.!?])\s+', text) if c.strip()]
            if not chunks:
                chunks = [text]

            total_chars     = sum(len(c) for c in chunks)
            processed_chars = 0
            all_samples     = []
            sample_rate     = 24000
            start_time      = time.time()

            for chunk in chunks:
                if self._stop_evt.is_set():
                    print("[TTS] Stopped during generation")
                    return

                samples, sr = kokoro.create(
                    chunk,
                    voice=self.voice,
                    speed=1.0,      # always generate at 1× — speed applied in _play_samples
                    lang="en-us",
                )
                if hasattr(samples, "tolist"):
                    all_samples.extend(samples.tolist())
                else:
                    all_samples.extend(samples)
                sample_rate = sr

                processed_chars += len(chunk)
                elapsed        = time.time() - start_time
                chars_per_sec  = processed_chars / elapsed if elapsed > 0 else 0
                remaining      = total_chars - processed_chars
                eta            = int(remaining / chars_per_sec) if chars_per_sec > 0 else 0
                if self._on_progress:
                    self._on_progress(processed_chars, total_chars, eta)

            if self._stop_evt.is_set():
                print("[TTS] Stopped before playback")
                return

            # ── 2. Notify UI that playback is about to start ─────────────────
            if self._on_playback_start:
                self._on_playback_start()

            print(f"[TTS] Playing {len(all_samples)/sample_rate:.1f}s of audio...")

            # ── 3. Interruptible playback ────────────────────────────────────
            completed = self._play_samples(all_samples, sample_rate)

            if completed:
                naturally_stopped = True
                print("[TTS] Playback complete")
            else:
                print("[TTS] Playback interrupted")

        except Exception as exc:
            import traceback
            print("[TTS] ERROR:", exc)
            traceback.print_exc()
            if self._on_error:
                self._on_error(str(exc))
        finally:
            self._speaking = False
            # Only fire on_stop for natural completion, not user-initiated stop
            if naturally_stopped and self._on_stop:
                self._on_stop()