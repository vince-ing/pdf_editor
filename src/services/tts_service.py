"""
TtsService — offline text-to-speech via kokoro-onnx 0.5.x.

Architecture: producer / consumer pipeline
─────────────────────────────────────────
  Generator thread  →  Queue[numpy array]  →  Player thread
                              ↑
                       bounded to 3 items so the generator
                       doesn't race too far ahead of playback

Text pipeline before synthesis:
  raw PDF text  →  _clean_text()  →  _split_text()  →  kokoro chunks

_clean_text normalises ligatures, curly quotes, hyphens, URLs, emails,
bullet markers, common abbreviations, all-caps headings, and stray symbols
so kokoro always receives clean, natural prose.

_split_text breaks the cleaned text into word-boundary chunks of ~40 words,
preferring sentence then clause punctuation as split points, with a hard cap
of 60 words and a minimum of 8 (short fragments are merged into the previous
chunk).

Speed is passed to kokoro.create() at generation time — kokoro's own speed
control is pitch-preserving (neural, not resampling), so voices sound natural
across the full 0.25–4.0× range.  Speed changes snapshot at chunk boundaries
(~4–8 s granularity), which is imperceptible in practice.

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

    # ── Text cleaning ─────────────────────────────────────────────────────────

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Sanitise PDF-extracted text so kokoro reads it naturally.

        Problems this addresses, in order:
          - Ligatures and Unicode oddities (ﬁ → fi, curly quotes → straight)
          - Hyphenated line-breaks from PDF reflow (re-\nfuse → refuse)
          - URLs, file paths, and email addresses (useless when read aloud)
          - Decimal numbers expanded to spoken form (23.5 → "23 point 5")
          - Unit symbols (°, %, ½ etc.) expanded before anything else touches them
          - Bullet / list markers stripped
          - Common symbols expanded (&, =, #, +, §, ©, etc.)
          - Common abbreviations expanded (Fig., Dr., e.g., etc.)
          - All-caps words softened to title-case (INTRODUCTION → Introduction)
          - Excessive whitespace collapsed
        """
        # ── 1. Unicode normalisation ──────────────────────────────────────────
        # Ligatures
        for lig, expanded in [
            ("\ufb00", "ff"), ("\ufb01", "fi"), ("\ufb02", "fl"),
            ("\ufb03", "ffi"), ("\ufb04", "ffl"), ("\ufb05", "st"),
            ("\u00e6", "ae"), ("\u0153", "oe"),
        ]:
            text = text.replace(lig, expanded)

        # Curly / typographic punctuation → ASCII equivalents
        text = text.replace("\u2018", "'").replace("\u2019", "'")   # ' '
        text = text.replace("\u201c", '"').replace("\u201d", '"')   # " "
        text = text.replace("\u2013", "-").replace("\u2014", ", ")  # – —
        text = text.replace("\u2026", "...")                         # …
        text = text.replace("\u00b7", "")                            # middle dot
        text = text.replace("\u00ad", "")                            # soft hyphen

        # ── 2. Hyphenated line-breaks (PDFs wrap mid-word with a hyphen) ──────
        # "re-\nfuse" → "refuse",  "self-\naware" → "self-aware" is ambiguous
        # so only collapse when the hyphen is immediately before a newline.
        text = re.sub(r'-\n(\S)', r'\1', text)

        # ── 3. Remaining newlines → space ─────────────────────────────────────
        text = text.replace("\n", " ").replace("\r", " ")

        # ── 4. URLs — remove entirely ─────────────────────────────────────────
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'www\.\S+', '', text)
        # Also strip bare file paths like /usr/local/bin/foo or C:\Windows\...
        text = re.sub(r'(?<!\w)[A-Za-z]:\\[\\\S]+', '', text)
        text = re.sub(r'(?<!\w)/[\w./\-]+', '', text)

        # ── 5. Email addresses ────────────────────────────────────────────────
        text = re.sub(r'\S+@\S+\.\S+', '', text)

        # ── 6. Decimal numbers → spoken form ─────────────────────────────────
        # Must run before unit-symbol expansion and the page-number stripper so
        # "23.5°" becomes "23 point 5 degrees" and the digits are never seen as
        # isolated page numbers.
        # Handles: 23.5 / 0.75 / 3.14159 / -1.5 / +2.0
        # Does NOT touch version strings like "3.2.1" (two dots) or plain
        # integers — only a single decimal point between digit groups.
        text = re.sub(
            r'(-?\+?\d+)\.(\d+)(?!\.\d)',   # one dot only, not "3.2.1"
            lambda m: m.group(1) + " point " + m.group(2),
            text,
        )

        # ── 7. Unit symbols — expand BEFORE the page-number stripper ─────────
        # "23 point 5°" → "23 point 5 degrees"
        # "72°F" → "72 degrees Fahrenheit"
        text = re.sub(
            r'(\d)\s*°\s*([CF])\b',
            lambda m: m.group(1) + " degrees " + ("Celsius" if m.group(2) == "C" else "Fahrenheit"),
            text,
        )
        text = re.sub(r'(\d)\s*°', r'\1 degrees ', text)
        text = text.replace("%", " percent ")

        # ── 8. Bullet / list markers ──────────────────────────────────────────
        # Symbolic bullets — safe to strip anywhere
        text = re.sub(r'(?:^|\s)[•·▪▸►◦‣⁃]\s*', ' ', text)
        # Alphanumeric list markers (1. / a.) — only strip when they follow
        # start-of-string or sentence-ending punctuation so that mid-sentence
        # constructs like "(C,A)" or "(x,y)" are never touched.
        text = re.sub(r'(?:(?:^|(?<=[.!?]))\s*)(?:\d+\.|[a-zA-Z]\))\s+', ' ', text)

        # ── 9. Other symbols ──────────────────────────────────────────────────
        text = text.replace("©", "").replace("®", "").replace("™", "")
        text = text.replace("§", "section ").replace("¶", "")
        text = text.replace("+", " plus ")
        text = text.replace("=", " equals ")
        text = text.replace("&", " and ")
        text = text.replace("@", " at ")
        text = text.replace("#", " number ")
        text = text.replace("½", "one half").replace("¼", "one quarter")
        text = text.replace("¾", "three quarters")

        # ── 10. Common abbreviations ──────────────────────────────────────────
        _ABBREV = [
            (r'\bFig\.',     "Figure"),
            (r'\bfig\.',     "figure"),
            (r'\bEq\.',      "Equation"),
            (r'\beq\.',      "equation"),
            (r'\bCh\.',      "Chapter"),
            (r'\bSec\.',     "Section"),
            (r'\bvol\.',     "volume"),
            (r'\bVol\.',     "Volume"),
            (r'\bpp\.',      "pages"),
            (r'\bp\.',       "page"),
            (r'\bno\.',      "number"),
            (r'\bNo\.',      "Number"),
            (r'\bvs\.',      "versus"),
            (r'\betc\.',     "et cetera"),
            (r'\be\.g\.',    "for example"),
            (r'\bi\.e\.',    "that is"),
            (r'\bapprox\.',  "approximately"),
            (r'\bDr\.',      "Doctor"),
            (r'\bProf\.',    "Professor"),
            (r'\bMr\.',      "Mister"),
            (r'\bMrs\.',     "Misses"),
            (r'\bMs\.',      "Ms"),
            (r'\bSt\.',      "Saint"),
            (r'\bAve\.',     "Avenue"),
            (r'\bBlvd\.',    "Boulevard"),
            (r'\bDept\.',    "Department"),
            (r'\bCorp\.',    "Corporation"),
            (r'\bInc\.',     "Incorporated"),
            (r'\bLtd\.',     "Limited"),
            (r'\bco\.',      "company"),
        ]
        for pattern, replacement in _ABBREV:
            text = re.sub(pattern, replacement, text)

        # ── 11. All-caps words → title-case ──────────────────────────────────
        # Short acronyms (CIA, PDF, TTS) are fine — kokoro reads them letter by
        # letter already.  Long all-caps words (INTRODUCTION, CONCLUSION) sound
        # robotic; title-casing them reads more naturally.
        def _maybe_titlecase(m: re.Match) -> str:
            w = m.group(0)
            return w.title() if len(w) > 4 else w
        text = re.sub(r'\b[A-Z]{5,}\b', _maybe_titlecase, text)

        # ── 12. Collapse whitespace ───────────────────────────────────────────
        text = re.sub(r'\s{2,}', ' ', text).strip()

        return text

    # ── Text splitting ────────────────────────────────────────────────────────

    @staticmethod
    def _split_text(text: str,
                    target_words: int = 40,
                    max_words:    int = 60,
                    min_words:    int = 8) -> list[str]:
        """
        Split *text* into chunks that are safe and natural for kokoro.

        Rules (in priority order):
          1. Never split inside a word — only ever at whitespace boundaries.
          2. Prefer splitting after sentence-ending punctuation (. ! ?).
          3. Fall back to clause punctuation (, ; : — –) when no sentence
             boundary exists within the target window.
          4. Fall back to any word boundary when there is no punctuation at all
             (handles raw OCR dumps, bullet lists, un-punctuated text, etc.).
          5. Merge any trailing fragment shorter than *min_words* into the
             previous chunk so kokoro is never fed a single word or two.

        target_words : ideal chunk size in words
        max_words    : hard ceiling — force a word-boundary split here
        min_words    : minimum size; shorter fragments are merged backward
        """
        words = text.split()
        if not words:
            return []

        sentence_end = re.compile(r'[.!?]["\'\u201d]?$')
        clause_break = re.compile(r'[,;:\u2014\u2013]["\'\u201d]?$')

        chunks: list[str] = []
        start = 0

        while start < len(words):
            ideal_end = min(start + target_words, len(words))
            hard_end  = min(start + max_words,    len(words))

            # Remaining words fit within the hard ceiling — take them all.
            if hard_end == len(words):
                chunks.append(" ".join(words[start:]))
                break

            split_at = None

            # 1. Sentence boundary — scan backwards from hard_end to ideal_end.
            for i in range(hard_end - 1, ideal_end - 1, -1):
                if sentence_end.search(words[i]):
                    split_at = i + 1
                    break

            # 2. Clause boundary in the same window.
            if split_at is None:
                for i in range(hard_end - 1, ideal_end - 1, -1):
                    if clause_break.search(words[i]):
                        split_at = i + 1
                        break

            # 3. No punctuation — cut at the ideal word boundary.
            if split_at is None:
                split_at = ideal_end

            chunks.append(" ".join(words[start:split_at]))
            start = split_at

        # Merge fragments that are too short into the previous chunk.
        merged: list[str] = []
        for chunk in chunks:
            if merged and len(chunk.split()) < min_words:
                merged[-1] = merged[-1] + " " + chunk
            else:
                merged.append(chunk)

        return [c.strip() for c in merged if c.strip()]

    # ── Generator thread ──────────────────────────────────────────────────────

    def _generator(self, text: str, q: queue.Queue) -> None:
        """
        Split text into chunks, generate audio for each, push into queue.
        Always pushes _SENTINEL last so the player knows generation is done.
        """
        try:
            if self._on_start:
                self._on_start()

            import numpy as np
            kokoro = self._load_kokoro()

            sentences = self._split_text(self._clean_text(text))
            if not sentences:
                sentences = [text]

            total = len(sentences)
            print(f"[TTS-gen] {total} chunk(s) to generate")

            for idx, sentence in enumerate(sentences):
                if self._stop_evt.is_set():
                    print("[TTS-gen] Stopped early")
                    return

                # Snapshot speed at generation time — kokoro's own speed
                # parameter is pitch-preserving (neural, not resampling).
                # Speed changes take effect at the next chunk boundary.
                speed = max(0.25, min(4.0, float(self.speed)))

                samples, sr = kokoro.create(
                    sentence,
                    voice=self.voice,
                    speed=speed,
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
        through a single persistent OutputStream.  Speed is handled by kokoro
        at generation time so the player just writes raw samples at a fixed rate.
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
        ticks, honouring pause and stop events.

        Speed is now handled by kokoro at generation time (pitch-preserving),
        so the player just writes raw samples at a fixed rate.

        Returns True if the sentence played to completion, False if interrupted.
        """
        import numpy as np

        total = len(samples)
        pos   = 0

        while pos < total:
            # stop
            if self._stop_evt.is_set():
                stream.abort()
                return False

            # pause — cuts audio immediately, blocks until resumed or stopped
            if not self._pause_evt.is_set():
                stream.stop()
                self._pause_evt.wait()
                if self._stop_evt.is_set():
                    return False
                stream.start()

            chunk = samples[pos: pos + _CHUNK_FRAMES]
            if len(chunk) == 0:
                break

            stream.write(chunk.astype(np.float32))
            pos += len(chunk)

        return True