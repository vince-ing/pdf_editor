"""
TtsService — offline text-to-speech via kokoro-onnx 0.5.x.

Architecture: producer / consumer pipeline
─────────────────────────────────────────
  Generator thread  →  Queue[numpy array]  →  Player thread
                              ↑
                       bounded to 3 items so the generator
                       doesn't race too far ahead of playback

The generator splits the text into sentences, calls kokoro.create() for
each one, and pushes the resulting audio array into the queue.  The player
pulls arrays out of the queue one at a time and streams them through a
single persistent OutputStream using the speed-resampling chunk loop from
before.  Because kokoro typically generates each sentence 3-5× faster than
realtime, playback starts after the very first sentence is ready (~0.3 s
for a short sentence) and subsequent sentences are waiting in the queue
before the current one finishes.

Pause / stop events are checked in the player's inner chunk loop (≤85 ms
latency) and in the generator's sentence loop (stops generation immediately).

Install: pip install kokoro-onnx soundfile sounddevice
"""

from __future__ import annotations

import os
import queue
import re
import threading
import urllib.request
from typing import Callable

# ── Model locations ───────────────────────────────────────────────────────────

_MODEL_URL  = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
_VOICES_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

_HERE         = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_CACHE_DIR    = os.path.join(_PROJECT_ROOT, "models", "kokoro")
_MODEL_PATH   = os.path.join(_CACHE_DIR, "kokoro-v1.0.onnx")
_VOICES_PATH  = os.path.join(_CACHE_DIR, "voices-v1.0.bin")

# ── Tuning constants ──────────────────────────────────────────────────────────

# Frames written to the OutputStream per loop tick.
# At 24 kHz, 2048 frames ≈ 85 ms — fast enough for responsive pause/stop.
_CHUNK_FRAMES = 2048

# Maximum number of pre-generated sentence arrays waiting in the queue.
# 3 gives a comfortable buffer without wasting memory on long documents.
_QUEUE_MAXSIZE = 3

# Sentinel pushed by the generator to tell the player it is done.
_SENTINEL = object()


def _download(url: str, dest: str, label: str) -> None:
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    print(f"[TTS] Downloading {label}…")
    urllib.request.urlretrieve(url, dest)
    print(f"[TTS] Saved to {dest}")


class TtsService:
    """
    Wraps kokoro-onnx 0.5.x for low-latency, streaming TTS playback.

    Callbacks (all called on worker threads — use root.after() to touch UI):
      on_start()                          generation has begun
      on_playback_start()                 first audio is about to play
      on_progress(done, total, pct)       sentences done / total / 0-100 int
      on_stop()                           natural completion (not user stop)
      on_error(msg)                       something went wrong
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
        self._pause_evt.set()          # clear = paused, set = playing
        self._speaking  = False

        # Both threads stored so stop() can join them
        self._gen_thread:  threading.Thread | None = None
        self._play_thread: threading.Thread | None = None

        self.voice = "af_alloy"
        self.speed = 1.0              # read live by the player every chunk tick

    # ── Public API ────────────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Start speaking *text*.  Stops any ongoing speech first.  Non-blocking."""
        self.stop()
        text = text.strip()
        if not text:
            return
        self._stop_evt.clear()
        self._pause_evt.set()
        self._speaking = True

        # Bounded queue shared between the two threads
        audio_queue: queue.Queue = queue.Queue(maxsize=_QUEUE_MAXSIZE)

        self._gen_thread = threading.Thread(
            target=self._generator, args=(text, audio_queue), daemon=True,
            name="tts-generator")
        self._play_thread = threading.Thread(
            target=self._player, args=(audio_queue,), daemon=True,
            name="tts-player")

        self._gen_thread.start()
        self._play_thread.start()

    def stop(self) -> None:
        """Stop immediately.  Blocks until both threads exit (at most ~300 ms)."""
        self._stop_evt.set()
        self._pause_evt.set()   # unblock a paused player so it sees stop
        for t in (self._gen_thread, self._play_thread):
            if t and t.is_alive():
                t.join(timeout=4.0)
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

    # ── Model helpers ─────────────────────────────────────────────────────────

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
                "kokoro-onnx not installed.\n"
                "Run: pip install kokoro-onnx soundfile sounddevice"
            )
        self._ensure_models()
        self._kokoro = Kokoro(_MODEL_PATH, _VOICES_PATH)
        return self._kokoro

    # ── Generator thread ──────────────────────────────────────────────────────

    def _generator(self, text: str, q: queue.Queue) -> None:
        """
        Split text into sentences, generate audio for each, push into queue.
        Always pushes _SENTINEL last so the player knows generation is done.
        """
        try:
            if self._on_start:
                self._on_start()

            import numpy as np
            kokoro = self._load_kokoro()

            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
            if not sentences:
                sentences = [text]

            total = len(sentences)
            print(f"[TTS-gen] {total} sentence(s) to generate")

            for idx, sentence in enumerate(sentences):
                if self._stop_evt.is_set():
                    print("[TTS-gen] Stopped early")
                    return

                samples, sr = kokoro.create(
                    sentence,
                    voice=self.voice,
                    speed=1.0,      # speed applied at playback time via resampling
                    lang="en-us",
                )

                arr = np.asarray(samples, dtype=np.float32)
                if arr.ndim == 1:
                    arr = arr.reshape(-1, 1)

                # Block until the player has room, but wake up on stop
                while True:
                    if self._stop_evt.is_set():
                        return
                    try:
                        q.put((arr, sr), timeout=0.1)
                        break
                    except queue.Full:
                        continue

                done = idx + 1
                pct  = int(done / total * 100)
                print(f"[TTS-gen] Generated sentence {done}/{total}")
                if self._on_progress:
                    self._on_progress(done, total, pct)

        except Exception as exc:
            import traceback
            print("[TTS-gen] ERROR:", exc)
            traceback.print_exc()
            if self._on_error:
                self._on_error(str(exc))
        finally:
            # Always send the sentinel so the player can exit cleanly
            try:
                q.put(_SENTINEL, timeout=1.0)
            except queue.Full:
                pass

    # ── Player thread ─────────────────────────────────────────────────────────

    def _player(self, q: queue.Queue) -> None:
        """
        Pull (samples, sample_rate) pairs from the queue and stream them
        through a single persistent OutputStream.  Speed resampling is
        applied per-chunk so slider changes take effect within ~85 ms.
        """
        import sounddevice as sd

        naturally_finished = False
        playback_started   = False
        stream             = None

        try:
            while True:
                if self._stop_evt.is_set():
                    break

                # Pull the next sentence (or sentinel) from the queue
                try:
                    item = q.get(timeout=0.1)
                except queue.Empty:
                    continue

                if item is _SENTINEL:
                    naturally_finished = True
                    break

                sentence_samples, sample_rate = item

                # Open the stream once, reuse it across all sentences to
                # avoid the ~20 ms device-open overhead between sentences
                if stream is None:
                    stream = sd.OutputStream(
                        samplerate=sample_rate,
                        channels=sentence_samples.shape[1],
                        dtype="float32",
                    )
                    stream.start()

                if not playback_started:
                    playback_started = True
                    if self._on_playback_start:
                        self._on_playback_start()

                completed = self._stream_samples(stream, sentence_samples)
                if not completed:
                    break

        except Exception as exc:
            import traceback
            print("[TTS-play] ERROR:", exc)
            traceback.print_exc()
            if self._on_error:
                self._on_error(str(exc))
        finally:
            if stream is not None:
                try:
                    stream.abort()
                    stream.close()
                except Exception:
                    pass
            self._speaking = False
            if naturally_finished and self._on_stop:
                self._on_stop()

    def _stream_samples(self, stream, samples) -> bool:
        """
        Write *samples* to the already-open *stream* in _CHUNK_FRAMES-sized
        ticks, applying live speed resampling and honouring pause/stop.

        Returns True if the sentence played to completion, False if interrupted.
        """
        import numpy as np

        total = len(samples)
        pos_f: float = 0.0

        while pos_f < total:
            # stop
            if self._stop_evt.is_set():
                stream.abort()
                return False

            # pause — cuts audio immediately, waits for resume
            if not self._pause_evt.is_set():
                stream.stop()
                self._pause_evt.wait()
                if self._stop_evt.is_set():
                    return False
                stream.start()

            # Speed-aware source window
            speed      = max(0.1, float(self.speed))
            src_frames = int(_CHUNK_FRAMES * speed)
            src_start  = int(pos_f)
            src_end    = min(src_start + src_frames, total)
            src_chunk  = samples[src_start:src_end]

            if len(src_chunk) == 0:
                break

            # Linear interpolation to stretch/compress to exactly _CHUNK_FRAMES
            src_len = len(src_chunk)
            if src_len != _CHUNK_FRAMES:
                out_idx   = np.linspace(0, src_len - 1, _CHUNK_FRAMES)
                lo        = np.floor(out_idx).astype(np.int32)
                hi        = np.minimum(lo + 1, src_len - 1)
                frac      = (out_idx - lo)[:, np.newaxis]
                src_chunk = src_chunk[lo] * (1.0 - frac) + src_chunk[hi] * frac

            stream.write(src_chunk.astype(np.float32))
            pos_f += src_frames

        return True