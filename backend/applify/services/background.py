"""In-process background jobs for the MVP (D10).

A single worker thread: LLM calls are serialized anyway, and the interface (submit a
callable) can later be backed by a real worker queue.
"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

log = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="applify-job")


class TaskRunner(Protocol):
    def __call__(self, fn: Callable[..., Any], /, *args: Any) -> None: ...


def _logged(fn: Callable[..., Any], *args: Any) -> None:
    try:
        fn(*args)
    except Exception:
        log.exception("background job %s failed", getattr(fn, "__name__", fn))


def submit(fn: Callable[..., Any], /, *args: Any) -> None:
    _executor.submit(_logged, fn, *args)


def get_task_runner() -> TaskRunner:
    return submit
