from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal, Slot

CoroutineFactory = Callable[[], Awaitable[Any]]
StreamFactory = Callable[[], AsyncIterator[Any]]
SuccessCallback = Callable[[Any], None]
ItemCallback = Callable[[Any], None]
ErrorCallback = Callable[[str], None]
DoneCallback = Callable[[], None]


class InlineTaskRunner:
    def submit(
        self,
        coroutine_factory: CoroutineFactory,
        *,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        try:
            result = asyncio.run(coroutine_factory())
        except Exception as exc:
            if on_error is not None:
                on_error(str(exc))
            return

        if on_success is not None:
            on_success(result)

    def stream(
        self,
        stream_factory: StreamFactory,
        *,
        on_item: ItemCallback | None = None,
        on_done: DoneCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        async def consume() -> None:
            async for item in stream_factory():
                if on_item is not None:
                    on_item(item)

        try:
            asyncio.run(consume())
        except Exception as exc:
            if on_error is not None:
                on_error(str(exc))
            return

        if on_done is not None:
            on_done()


class _CoroutineWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, coroutine_factory: CoroutineFactory) -> None:
        super().__init__()
        self._coroutine_factory = coroutine_factory

    @Slot()
    def run(self) -> None:
        try:
            result = asyncio.run(self._coroutine_factory())
        except Exception as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
        finally:
            self.finished.emit()


class _StreamWorker(QObject):
    item = Signal(object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, stream_factory: StreamFactory) -> None:
        super().__init__()
        self._stream_factory = stream_factory

    @Slot()
    def run(self) -> None:
        async def consume() -> None:
            async for payload in self._stream_factory():
                self.item.emit(payload)

        try:
            asyncio.run(consume())
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.finished.emit()


class QtAsyncRunner:
    def __init__(self) -> None:
        self._active_threads: set[QThread] = set()

    def submit(
        self,
        coroutine_factory: CoroutineFactory,
        *,
        on_success: SuccessCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        worker = _CoroutineWorker(coroutine_factory)
        thread = self._build_thread(worker)
        if on_success is not None:
            worker.succeeded.connect(on_success)
        if on_error is not None:
            worker.failed.connect(on_error)
        thread.start()

    def stream(
        self,
        stream_factory: StreamFactory,
        *,
        on_item: ItemCallback | None = None,
        on_done: DoneCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        worker = _StreamWorker(stream_factory)
        thread = self._build_thread(worker)
        if on_item is not None:
            worker.item.connect(on_item)
        if on_done is not None:
            worker.finished.connect(on_done)
        if on_error is not None:
            worker.failed.connect(on_error)
        thread.start()

    def _build_thread(self, worker: QObject) -> QThread:
        thread = QThread()
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda: self._active_threads.discard(thread))
        self._active_threads.add(thread)
        return thread

    def shutdown(self, timeout_ms: int = 5000) -> None:
        for thread in list(self._active_threads):
            thread.quit()
        for thread in list(self._active_threads):
            thread.wait(timeout_ms)
