"""Background generation jobs with progress, cancellation and one-at-a-time scheduling.

Jobs run in daemon threads and never touch Streamlit; the UI polls ``snapshot()``.
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass
from enum import Enum

from ..errors import JobCancelled
from .pipeline import GenerationRequest, GenerationResult, run_generation

log = logging.getLogger(__name__)


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLING = "cancelling"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = (JobState.DONE, JobState.FAILED, JobState.CANCELLED)


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    title: str
    state: JobState
    completed: int
    total: int
    message: str
    error: str | None
    result: GenerationResult | None
    elapsed: float
    eta: float | None

    @property
    def percent(self) -> float:
        return (self.completed / self.total) if self.total else 0.0

    @property
    def finished(self) -> bool:
        return self.state in TERMINAL


class SynthesisJob:
    def __init__(self, request: GenerationRequest) -> None:
        self.id = uuid.uuid4().hex[:12]
        self.request = request
        self.cancel_event = threading.Event()
        self._lock = threading.Lock()
        self._state = JobState.QUEUED
        self._completed = 0
        self._total = 0
        self._message = "Waiting to start…"
        self._error: str | None = None
        self._result: GenerationResult | None = None
        self._created = time.monotonic()
        self._started: float | None = None
        self._finished: float | None = None

    def _set(self, **fields) -> None:
        with self._lock:
            for key, value in fields.items():
                setattr(self, f"_{key}", value)

    def on_progress(self, done: int, total: int, message: str) -> None:
        self._set(completed=done, total=total, message=message)

    def snapshot(self) -> JobSnapshot:
        with self._lock:
            now = time.monotonic()
            started = self._started
            end = self._finished or now
            elapsed = (end - started) if started else 0.0
            eta = None
            if started and self._state == JobState.RUNNING and self._completed > 0 and self._total:
                eta = elapsed / self._completed * (self._total - self._completed)
            return JobSnapshot(
                id=self.id,
                title=self.request.display_title,
                state=self._state,
                completed=self._completed,
                total=self._total,
                message=self._message,
                error=self._error,
                result=self._result,
                elapsed=elapsed,
                eta=eta,
            )


class JobManager:
    """Runs jobs one at a time (speech synthesis is CPU heavy) and keeps recent jobs for polling."""

    def __init__(self) -> None:
        self._jobs: dict[str, SynthesisJob] = {}
        self._lock = threading.Lock()
        self._gate = threading.Semaphore(1)

    def submit(self, request: GenerationRequest) -> SynthesisJob:
        job = SynthesisJob(request)
        with self._lock:
            self._jobs[job.id] = job
            self._prune()
        threading.Thread(target=self._run, args=(job,), name=f"job-{job.id}", daemon=True).start()
        return job

    def get(self, job_id: str | None) -> SynthesisJob | None:
        if not job_id:
            return None
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> None:
        job = self.get(job_id)
        if job is None:
            return
        job.cancel_event.set()
        if job.snapshot().state == JobState.RUNNING:
            job._set(state=JobState.CANCELLING, message="Cancelling after the current part…")

    def active(self) -> SynthesisJob | None:
        with self._lock:
            for job in self._jobs.values():
                if not job.snapshot().finished:
                    return job
        return None

    def _prune(self) -> None:
        finished = [j for j in self._jobs.values() if j.snapshot().finished]
        for job in finished[:-20]:
            self._jobs.pop(job.id, None)

    def _run(self, job: SynthesisJob) -> None:
        with self._gate:
            if job.cancel_event.is_set():
                job._set(state=JobState.CANCELLED, message="Cancelled before it started.", finished=time.monotonic())
                return
            job._set(state=JobState.RUNNING, message="Starting…", started=time.monotonic())
            try:
                result = run_generation(job.request, job.cancel_event, job.on_progress)
                job._set(state=JobState.DONE, result=result, message="Finished.", finished=time.monotonic())
            except JobCancelled:
                job._set(state=JobState.CANCELLED, message="Cancelled.", finished=time.monotonic())
            except Exception as exc:  # recorded for the UI; details already logged by the pipeline
                log.debug("Job %s failed", job.id, exc_info=True)
                job._set(state=JobState.FAILED, error=str(exc), message="Failed.", finished=time.monotonic())


_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    global _manager
    with _manager_lock:
        if _manager is None:
            _manager = JobManager()
        return _manager
