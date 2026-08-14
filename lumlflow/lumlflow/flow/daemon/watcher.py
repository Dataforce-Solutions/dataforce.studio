from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Protocol

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .reconcile import Reconciler, ReconciliationResult, is_observed_path


class ObserverLike(Protocol):
    def schedule(
        self, event_handler: FileSystemEventHandler, path: str, *, recursive: bool
    ) -> object: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...


class _EventHandler(FileSystemEventHandler):
    def __init__(self, watcher: FlowWatcher) -> None:
        self.watcher = watcher

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        self.watcher.notify_from_thread(Path(os.fsdecode(event.src_path)))
        destination = getattr(event, "dest_path", "")
        if destination:
            self.watcher.notify_from_thread(Path(os.fsdecode(destination)))


class FlowWatcher:
    def __init__(
        self,
        reconciler: Reconciler,
        *,
        debounce_seconds: float = 2.0,
        observer: ObserverLike | None = None,
    ) -> None:
        self.reconciler = reconciler
        self.flow_dir = reconciler.store.flow_dir.resolve()
        self.debounce_seconds = debounce_seconds
        self.observer = observer or Observer()
        self.loop: asyncio.AbstractEventLoop | None = None
        self._paths: set[Path] = set()
        self._actors: set[str] = set()
        self._handle: asyncio.TimerHandle | None = None
        self._explicit_actor: str | None = None
        self._explicit_intent: str | None = None
        self._started = False

    def start(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        if self._started:
            return
        self.loop = loop or asyncio.get_running_loop()
        self.observer.schedule(_EventHandler(self), str(self.flow_dir), recursive=True)
        self.observer.start()
        self._started = True

    def stop(self) -> None:
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        if self._started:
            self.observer.stop()
            self.observer.join(timeout=5)
            self._started = False

    def begin(self, actor: str, *, intent: str | None = None) -> None:
        self._explicit_actor = actor
        self._explicit_intent = intent

    def end(self, actor: str) -> ReconciliationResult:
        if self._explicit_actor != actor:
            raise ValueError(f"no watcher bracket for actor {actor}")
        result = self.flush(actor=actor, intent=self._explicit_intent)
        self._explicit_actor = None
        self._explicit_intent = None
        return result

    def notify_from_thread(self, path: Path, actor: str | None = None) -> None:
        if self.loop is None:
            return
        self.loop.call_soon_threadsafe(self.notify, path, actor)

    def notify(self, path: Path, actor: str | None = None) -> None:
        if not is_observed_path(self.flow_dir, path):
            return
        self._paths.add(path.resolve())
        self._actors.add(actor or self._explicit_actor or "user")
        if self._explicit_actor is not None:
            return
        if self._handle is not None:
            self._handle.cancel()
        if self.loop is None:
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                return
        self._handle = self.loop.call_later(self.debounce_seconds, self.flush)

    def flush(
        self,
        *,
        actor: str | None = None,
        intent: str | None = None,
    ) -> ReconciliationResult:
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        paths = set(self._paths)
        actors = set(self._actors)
        self._paths.clear()
        self._actors.clear()
        if not paths:
            return ReconciliationResult([], [], [], [])
        attributed_actor = actor or (next(iter(actors)) if len(actors) == 1 else "user")
        return self.reconciler.reconcile(
            "live",
            paths=paths,
            actor=attributed_actor,
            intent=intent,
            mixed_editing=len(actors) > 1,
        )

    def quiesce(self, *, actor: str | None = None) -> ReconciliationResult:
        if self._handle is not None:
            self._handle.cancel()
            self._handle = None
        self._paths.clear()
        self._actors.clear()
        return self.reconciler.reconcile("quiesce", actor=actor)
