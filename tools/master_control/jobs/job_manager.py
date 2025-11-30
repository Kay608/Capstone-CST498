"""In-memory job registry for orchestrating remote operations."""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import field
from enum import Enum, auto
from typing import Dict, Iterable, Optional


from ..compat import dataclass


class JobStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(slots=True)
class Job:
    job_id: str
    label: str
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    return_code: Optional[int] = None
    message: str = ""
    metadata: Dict[str, str] = field(default_factory=dict)

    def mark_running(self) -> None:
        self.status = JobStatus.RUNNING
        now = time.time()
        self.started_at = now
        self.updated_at = now

    def mark_completed(self, message: str = "", return_code: int = 0) -> None:
        self.status = JobStatus.COMPLETED
        self.message = message
        self.return_code = return_code
        self.finished_at = time.time()
        self.updated_at = self.finished_at

    def mark_failed(self, message: str, return_code: int = 1) -> None:
        self.status = JobStatus.FAILED
        self.message = message
        self.return_code = return_code
        self.finished_at = time.time()
        self.updated_at = self.finished_at

    def mark_cancelled(self, message: str = "Cancelled") -> None:
        self.status = JobStatus.CANCELLED
        self.message = message
        self.finished_at = time.time()
        self.updated_at = self.finished_at


class JobManager:
    """Tracks lifecycle of orchestrated jobs."""

    def __init__(self) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, label: str, *, metadata: Optional[Dict[str, str]] = None) -> Job:
        with self._lock:
            job_id = uuid.uuid4().hex
            job = Job(job_id=job_id, label=label, metadata=metadata or {})
            self._jobs[job_id] = job
            return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> Iterable[Job]:
        with self._lock:
            return list(self._jobs.values())

    def mark_running(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.mark_running()
            return job

    def mark_completed(self, job_id: str, *, message: str = "", return_code: int = 0) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.mark_completed(message, return_code)
            return job

    def mark_failed(self, job_id: str, *, message: str, return_code: int = 1) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.mark_failed(message, return_code)
            return job

    def cancel(self, job_id: str, *, message: str = "Cancelled") -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.mark_cancelled(message)
            return job

    def clear(self) -> None:
        with self._lock:
            self._jobs.clear()
