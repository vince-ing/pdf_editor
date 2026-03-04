"""
DocumentSnapshot — disk-backed undo snapshot.

Writes the full document to a temporary file on disk rather than holding
bytes in RAM. The file is deleted as soon as the snapshot is no longer
needed (eager cleanup), with a __del__ safety net for anything that slips
through.
"""

import os
import tempfile
import fitz


class DocumentSnapshot:
    """
    Captures the state of a PDFDocument to a temporary file on disk.

    Usage
    -----
        snap = DocumentSnapshot(doc)   # written to disk immediately
        # ... mutate doc ...
        snap.restore(doc)              # doc reverts to captured state
        snap.cleanup()                 # temp file deleted

    The snapshot is stored in the OS temp directory and is cleaned up:
      • Eagerly, via an explicit cleanup() call from the history manager.
      • As a fallback, via __del__ if the object is garbage-collected without
        cleanup() having been called (e.g. on unexpected exit).
    """

    def __init__(self, doc):
        # NamedTemporaryFile with delete=False so we control the lifetime.
        fd, self._path = tempfile.mkstemp(suffix=".snap.pdf", prefix="pdfed_")
        os.close(fd)
        try:
            doc._doc.save(self._path, garbage=0, deflate=False)
        except Exception:
            self._safe_delete()
            raise

    def restore(self, doc):
        """Replace doc._doc with the snapshotted document, in place."""
        if self._path is None or not os.path.exists(self._path):
            raise FileNotFoundError("Snapshot file missing — cannot undo.")
        old = doc._doc
        doc._doc = fitz.open(self._path)
        if not old.is_closed:
            old.close()

    def cleanup(self):
        """Delete the temporary file. Safe to call multiple times."""
        self._safe_delete()

    def _safe_delete(self):
        if self._path and os.path.exists(self._path):
            try:
                os.remove(self._path)
            except OSError:
                pass
        self._path = None

    def __del__(self):
        self._safe_delete()