import asyncio
import heapq
import itertools
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass
class _Job[T]:
    key: str
    branch: str
    work: Callable[[], Awaitable[T]]
    waiters: set[asyncio.Future[T]] = field(default_factory=set)
    task: asyncio.Future[T] | None = None


class SerialPriorityQueue[T]:
    def __init__(self, *, active_branch: str | None = None) -> None:
        self.active_branch = active_branch
        self._jobs: dict[str, _Job[T]] = {}
        self._pending: list[tuple[int, int, str]] = []
        self._sequence = itertools.count()
        self._worker: asyncio.Task[None] | None = None

    def set_active_branch(self, branch: str) -> None:
        self.active_branch = branch
        self._pending = [
            (self._priority(self._jobs[key].branch), sequence, key)
            for _priority, sequence, key in self._pending
            if key in self._jobs
        ]
        heapq.heapify(self._pending)

    async def run(
        self,
        key: str,
        branch: str,
        work: Callable[[], Awaitable[T]],
    ) -> T:
        loop = asyncio.get_running_loop()
        waiter = loop.create_future()
        job = self._jobs.get(key)
        if job is None:
            job = _Job(key=key, branch=branch, work=work)
            self._jobs[key] = job
            heapq.heappush(
                self._pending,
                (self._priority(branch), next(self._sequence), key),
            )
        job.waiters.add(waiter)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._work_loop())
        try:
            return await asyncio.shield(waiter)
        finally:
            if not waiter.done():
                waiter.cancel()
            job.waiters.discard(waiter)

    def request_preemption(self, key: str) -> bool:
        job = self._jobs.get(key)
        if job is None or any(not waiter.cancelled() for waiter in job.waiters):
            return False
        if job.task is not None and not job.task.done():
            job.task.cancel()
        self._jobs.pop(key, None)
        return True

    @property
    def in_flight_keys(self) -> frozenset[str]:
        return frozenset(self._jobs)

    async def _work_loop(self) -> None:
        while self._pending:
            _priority, _sequence, key = heapq.heappop(self._pending)
            job = self._jobs.get(key)
            if job is None:
                continue
            if not job.waiters:
                self._jobs.pop(key, None)
                continue
            job.task = asyncio.ensure_future(job.work())
            try:
                result = await job.task
            except asyncio.CancelledError:
                for waiter in job.waiters:
                    if not waiter.done():
                        waiter.cancel()
            except Exception as error:
                for waiter in job.waiters:
                    if not waiter.done():
                        waiter.set_exception(error)
            else:
                for waiter in job.waiters:
                    if not waiter.done():
                        waiter.set_result(result)
            finally:
                self._jobs.pop(key, None)

    def _priority(self, branch: str) -> int:
        return 0 if branch == self.active_branch else 1
