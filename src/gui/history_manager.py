"""
HistoryManager — undo/redo stack for PDF editor commands.

Maintains a bounded history list of Command objects. When the stack is full
the oldest entry is evicted and its resources cleaned up. Discarded forward
history (after a new action) is also cleaned up immediately.
"""

from src.gui.theme import MAX_UNDO_STEPS


class HistoryManager:
    """
    Manages an undo/redo stack of Command objects.

    Usage
    -----
        hm = HistoryManager(on_change=self._on_history_change)
        hm.push(cmd)
        hm.undo()
        hm.redo()
        hm.clear()
    """

    def __init__(self, on_change=None):
        """
        Parameters
        ----------
        on_change : callable | None
            Called (with no arguments) after every push/undo/redo/clear so the
            caller can update dirty flags, titles, thumbnails, etc.
        """
        self._history: list    = []
        self._idx: int         = -1
        self._on_change        = on_change

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def can_undo(self) -> bool:
        return self._idx >= 0

    @property
    def can_redo(self) -> bool:
        return self._idx < len(self._history) - 1

    def push(self, cmd) -> None:
        """Record a newly executed command, discarding any forward history."""
        # Discard and clean up any commands after the current position
        discarded = self._history[self._idx + 1:]
        for old in discarded:
            old.cleanup()
        self._history = self._history[:self._idx + 1]

        # Evict the oldest entry if at capacity
        if len(self._history) >= MAX_UNDO_STEPS:
            evicted = self._history.pop(0)
            evicted.cleanup()
            self._idx = max(-1, self._idx - 1)

        self._history.append(cmd)
        self._idx = len(self._history) - 1
        self._notify()

    def undo(self):
        """
        Undo the most recent command.

        Returns
        -------
        str
            A human-readable label for the action that was undone, or an empty
            string if nothing was undone.

        Raises
        ------
        IndexError
            If there is nothing left to undo.
        """
        if not self.can_undo:
            raise IndexError("Nothing to undo.")
        cmd = self._history[self._idx]
        cmd.undo()
        self._idx -= 1
        self._notify()
        return self._label(cmd)

    def redo(self):
        """
        Re-execute the next command in the forward stack.

        Returns
        -------
        str
            A human-readable label for the action that was redone.

        Raises
        ------
        IndexError
            If there is nothing to redo.
        """
        if not self.can_redo:
            raise IndexError("Nothing to redo.")
        cmd = self._history[self._idx + 1]
        cmd.execute()
        self._idx += 1
        self._notify()
        return self._label(cmd)

    def clear(self) -> None:
        """Clean up all commands and reset the stack."""
        for cmd in self._history:
            cmd.cleanup()
        self._history.clear()
        self._idx = -1
        self._notify()

    # ── internals ─────────────────────────────────────────────────────────────

    def _notify(self):
        if self._on_change:
            self._on_change()

    @staticmethod
    def _label(cmd) -> str:
        return (
            type(cmd).__name__
            .replace("Command", "")
            .replace("Insert", "Insert ")
            .strip()
        )