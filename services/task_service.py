"""Producer-consumer background tasks. Workers never touch Tk widgets."""
from __future__ import annotations

import itertools
import logging
import queue
import threading
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable

log = logging.getLogger(__name__)


class EventKind(StrEnum):
    PROGRESS = "progress"
    RESULT = "result"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class TaskEvent:
    task_id: int
    kind: EventKind
    payload: Any = None
    message: str = ""


class TaskCancelled(Exception):
    """Raised inside a worker when cancellation was requested."""


class TaskContext:
    """Handle passed to the worker function."""

    def __init__(self, task_id: int, events: "queue.Queue[TaskEvent]", cancel: threading.Event) -> None:
        self.task_id = task_id
        self._events = events
        self._cancel = cancel

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def raise_if_cancelled(self) -> None:
        if self._cancel.is_set():
            raise TaskCancelled

    def progress(self, percent: float, message: str = "") -> None:
        self.raise_if_cancelled()
        self._events.put(TaskEvent(self.task_id, EventKind.PROGRESS, percent, message))


class TaskService:
    """Submit work to threads; drain events from the main thread via poll()."""

    def __init__(self) -> None:
        self._events: queue.Queue[TaskEvent] = queue.Queue()
        self._ids = itertools.count(1)
        self._threads: dict[int, threading.Thread] = {}
        self._cancels: dict[int, threading.Event] = {}
        self._handlers: dict[int, Callable[[TaskEvent], None]] = {}
        self._lock = threading.Lock()

    def submit(self, func: Callable[..., Any], *args: Any,
               on_event: Callable[[TaskEvent], None] | None = None, **kwargs: Any) -> int:
        """Run func(ctx, *args, **kwargs) in a worker thread; return the task id."""
        task_id = next(self._ids)
        cancel = threading.Event()
        thread = threading.Thread(target=self._run, args=(task_id, func, cancel, args, kwargs),
                                  name=f"task-{task_id}", daemon=True)
        with self._lock:
            self._threads[task_id] = thread
            self._cancels[task_id] = cancel
            if on_event:
                self._handlers[task_id] = on_event
        thread.start()
        return task_id

    def _run(self, task_id: int, func: Callable[..., Any], cancel: threading.Event,
             args: tuple, kwargs: dict) -> None:
        ctx = TaskContext(task_id, self._events, cancel)
        try:
            self._events.put(TaskEvent(task_id, EventKind.RESULT, func(ctx, *args, **kwargs)))
        except TaskCancelled:
            self._events.put(TaskEvent(task_id, EventKind.CANCELLED))
        except Exception as exc:  # noqa: BLE001 - delivered to the UI
            log.exception("Task %s failed", task_id)
            self._events.put(TaskEvent(task_id, EventKind.ERROR, exc, str(exc)))

    def cancel(self, task_id: int) -> None:
        with self._lock:
            event = self._cancels.get(task_id)
        if event:
            event.set()

    def poll(self, max_events: int = 100) -> list[TaskEvent]:
        """Drain pending events (main thread) and dispatch per-task handlers."""
        drained: list[TaskEvent] = []
        for _ in range(max_events):
            try:
                event = self._events.get_nowait()
            except queue.Empty:
                break
            drained.append(event)
            with self._lock:
                handler = self._handlers.get(event.task_id)
                if event.kind is not EventKind.PROGRESS:
                    self._handlers.pop(event.task_id, None)
                    self._cancels.pop(event.task_id, None)
                    self._threads.pop(event.task_id, None)
            if handler:
                handler(event)
        return drained

    def shutdown(self, timeout: float = 2.0) -> None:
        """Request cancellation of all tasks and join their threads."""
        with self._lock:
            events, threads = list(self._cancels.values()), list(self._threads.values())
        for e in events:
            e.set()
        for t in threads:
            t.join(timeout)
