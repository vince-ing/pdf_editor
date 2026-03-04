"""
HistoryManager — undo/redo stack for PDF editor commands.

Maintains a bounded history list of Command objects. When the stack is full
the oldest entry is evicted and its resources cleaned up. Discarded forward
history (after a new action) is also cleaned up immediately.

Navigation contract
-------------------
Commands capture a page_index at construction time. If the user navigates
to a different page the existing stack entries become unsafe to undo (they
would restore a snapshot taken on a different page while the user is looking
at another). Call ``clear_for_navigation()`` from ``_navigate_to()`` to
discard the stack before the page changes. This is intentionally distinct
from ``clear()`` so callers can tell the two cases apart if needed.

Dirty-since-save tracking
--------------------------
``push()`` sets an internal flag indicating the stack has grown since the
last save. ``mark_saved()`` resets it. ``is_dirty_since_save`` lets the
undo path (Step 5) warn the user before they undo past a save point.
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
        hm.clear_for_navigation()   # call before changing pages
        hm.mark_saved()             # call after a successful save
    """

    def __init__(self, on_change=None):
        """
        Parameters
        ----------
        on_change : callable | None
            Called (with no arguments) after every push/undo/redo/clear so the
            caller can update dirty flags, titles, thumbnails, etc.
        """
        self._history: list  = []
        self._idx: int       = -1
        self._on_change      = on_change
        self._dirty_since_save = False

    # ── public API ────────────────────────────────────────────────────────────

    @property
    def can_undo(self) -> bool:
        return self._idx >= 0

    @property
    def can_redo(self) -> bool:
        return self._idx < len(self._history) - 1

    @property
    def is_dirty_since_save(self) -> bool:
        """
        True if any command has been pushed since the last ``mark_saved()``
        call (or since construction). Used by the undo path to warn the user
        that undoing will take the document behind its last saved state.
        """
        return self._dirty_since_save

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
        self._dirty_since_save = True
        self._notify()

    def undo(self):
        """
        Undo the most recent command.

        Returns
        -------
        str
            A human-readable label for the action that was undone.

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
        """
        Clean up all commands and reset the stack.

        Call when a new document is opened or the app exits.
        """
        self._discard_all()
        self._dirty_since_save = False
        self._notify()

    def clear_for_navigation(self) -> None:
        """
        Discard the undo stack because the user is navigating to a different page.

        Commands hold page-specific snapshots. Allowing undo across a page
        navigation would restore a snapshot taken on page N while the user is
        looking at page M, producing a silent, confusing corruption. Clearing
        here is the correct safety contract.

        This is intentionally separate from ``clear()`` so callers can
        distinguish the two cases (e.g. to show a different status message or
        to skip resetting the dirty-since-save flag, as we do here — the
        document content hasn't changed, only the view).
        """
        self._discard_all()
        # Do NOT reset _dirty_since_save: the document may still have unsaved
        # changes from before the navigation; we don't want to lose that signal.
        self._notify()

    def mark_saved(self) -> None:
        """
        Record that the document has just been saved successfully.

        Resets ``is_dirty_since_save`` so the undo warning (Step 5) only
        fires when the user tries to undo past the current save point.
        """
        self._dirty_since_save = False
        # No _notify() — the save state is not something tools listen for.

    # ── internals ─────────────────────────────────────────────────────────────

    def _discard_all(self) -> None:
        """Clean up every command and reset stack pointers. Does not notify."""
        for cmd in self._history:
            cmd.cleanup()
        self._history.clear()
        self._idx = -1

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