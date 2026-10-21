"""In-process background jobs for the MVP (D10).

One worker thread for LLM jobs (they are serialized anyway) and one for search runs, so
a long run does not hold up a CV extraction. The interface (submit a callable) can later
be backed by a real worker queue.

The workers are daemon threads: a shutdown or dev reload must not wait for a search run
that takes minutes. Interrupted jobs are marked as failed at the next start.
"""

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any, Protocol

log = logging.getLogger(__name__)

Job = tuple[Callable[..., Any], tuple[Any, ...]]


class TaskRunner(Protocol):
    def __call__(self, fn: Callable[..., Any], /, *args: Any) -> None: ...


def _logged(fn: Callable[..., Any], *args: Any) -> None:
    try:
        fn(*args)
    except Exception:
        log.exception("background job %s failed", getattr(fn, "__name__", fn))


class _Worker:
    """A single daemon thread working through a queue, started on first use."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._queue: queue.SimpleQueue[Job] = queue.SimpleQueue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def submit(self, fn: Callable[..., Any], /, *args: Any) -> None:
        self._queue.put((fn, args))
        with self._lock:
            if self._thread is None:
                self._thread = threading.Thread(target=self._loop, name=self._name, daemon=True)
                self._thread.start()

    def _loop(self) -> None:
        while True:
            fn, args = self._queue.get()
            _logged(fn, *args)


_jobs = _Worker("applify-job")
_searches = _Worker("applify-search")


def get_task_runner() -> TaskRunner:
    return _jobs.submit


def get_search_runner() -> TaskRunner:
    return _searches.submit
