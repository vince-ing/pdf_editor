"""
MacroCommand — composite command that groups multiple commands into a single
undoable step.

Used by cross-page bulk redaction: each page needs its own BulkRedactCommand
(because each command's snapshot covers exactly one page's state), but the
entire multi-page operation should be one entry in the undo stack so the user
can undo all pages at once with a single Ctrl+Z.

Execute semantics
-----------------
execute() runs all child commands in order.  If any child raises, the
commands that already ran are rolled back (undone in reverse order) before
the exception propagates, leaving the document in its original state.

Undo semantics
--------------
undo() runs child.undo() in reverse order, which is the correct sequence for
restoring document state (last applied → first applied).

Cleanup
-------
cleanup() delegates to every child so all snapshot temp files are released.
"""

from __future__ import annotations

from src.commands.base import Command


class MacroCommand(Command):
    """
    Composite command — groups a list of commands into one undo step.

    Parameters
    ----------
    commands : list[Command]
        Child commands to execute in order.  Must be non-empty.
    label : str, optional
        Human-readable description used by HistoryManager._label() fallback.
    """

    def __init__(self, commands: list[Command], label: str = "Macro") -> None:
        if not commands:
            raise ValueError("MacroCommand requires at least one child command.")
        self._commands: list[Command] = list(commands)
        self._label    = label

    def execute(self) -> None:
        """
        Execute all child commands in order.

        If a child raises, already-executed children are undone in reverse
        order before re-raising so the document is left clean.
        """
        executed: list[Command] = []
        try:
            for cmd in self._commands:
                cmd.execute()
                executed.append(cmd)
        except Exception:
            # Roll back whatever succeeded
            for cmd in reversed(executed):
                try:
                    cmd.undo()
                except Exception:
                    pass  # best-effort rollback; original exception takes priority
            raise

    def undo(self) -> None:
        """Undo all child commands in reverse execution order."""
        for cmd in reversed(self._commands):
            cmd.undo()

    def cleanup(self) -> None:
        """Release resources held by all child commands."""
        for cmd in self._commands:
            cmd.cleanup()

    def __repr__(self) -> str:  # pragma: no cover
        return f"MacroCommand({self._label!r}, {len(self._commands)} commands)"