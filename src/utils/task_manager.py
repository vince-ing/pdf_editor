"""
task_manager.py — Thread-safe background worker for Tkinter.
"""

import threading
import queue
import tkinter as tk
from typing import Callable, Any

class BackgroundTaskManager:
    """
    Executes heavy operations in a background thread and routes the results
    safely back to the Tkinter main thread to prevent UI freezing.
    """
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self._queue = queue.Queue()
        self._check_queue()

    def _check_queue(self) -> None:
        """Poll the queue every 100ms for completed tasks."""
        try:
            while True:
                callback, args = self._queue.get_nowait()
                callback(*args)
        except queue.Empty:
            pass
        self.root.after(100, self._check_queue)

    def run_task(
        self, 
        worker_func: Callable[[], Any], 
        on_complete: Callable[[Any], None], 
        on_error: Callable[[Exception], None] = None
    ) -> None:
        """
        Run `worker_func` in a thread. When finished, pass its return value 
        to `on_complete` on the main thread.
        """
        def _thread_target():
            try:
                result = worker_func()
                self._queue.put((on_complete, (result,)))
            except Exception as e:
                if on_error:
                    self._queue.put((on_error, (e,)))
                else:
                    print(f"Background Task Error: {e}")

        threading.Thread(target=_thread_target, daemon=True).start()