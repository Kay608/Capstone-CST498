"""Background job scheduler that integrates with the job manager."""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Callable, Dict, Optional

from .jobs import JobManager


class JobScheduler:
    def __init__(self, job_manager: JobManager, *, max_workers: int = 4) -> None:
        self._jobs = job_manager
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="mc-job")
        self._futures: Dict[str, Future[Any]] = {}
        self._lock = threading.Lock()

    def submit(
        self,
        label: str,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> str:
        job = self._jobs.create_job(label)

        def _runner() -> Any:
            self._jobs.mark_running(job.job_id)
            try:
                result = func(*args, **kwargs)
                message = "Completed"
                if isinstance(result, str):
                    stripped = result.strip()
                    if stripped:
                        message = stripped.splitlines()[0]
                    else:
                        message = "Completed"
                elif result is not None:
                    message = str(result)
                self._jobs.mark_completed(job.job_id, message=message, return_code=0)
                return result
            except Exception as exc:  # pragma: no cover - defensive logging hook
                self._jobs.mark_failed(job.job_id, message=str(exc))
                raise
            finally:
                with self._lock:
                    self._futures.pop(job.job_id, None)

        future = self._executor.submit(_runner)
        with self._lock:
            self._futures[job.job_id] = future
        return job.job_id

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            future = self._futures.get(job_id)
        if not future:
            self._jobs.cancel(job_id)
            return False
        cancelled = future.cancel()
        if cancelled:
            self._jobs.cancel(job_id)
        return cancelled

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
