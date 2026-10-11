"""Recovery queue scheduling and multi-job monitor (290, 297)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from usb_recovery.util import isoformat, new_id


@dataclass
class Job:
    id: str
    kind: str
    label: str
    priority: int = 100
    status: str = "queued"
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    payload: dict = field(default_factory=dict)


class JobQueue:
    def __init__(self) -> None:
        self.jobs: list[Job] = []

    def add(self, kind: str, label: str, *, priority: int = 100, payload: dict | None = None) -> Job:
        job = Job(id=new_id("job-"), kind=kind, label=label, priority=priority, payload=payload or {})
        self.jobs.append(job)
        self.jobs.sort(key=lambda j: (j.priority, j.id))
        return job

    def run_sequential(self, handlers: dict[str, Callable[[Job], None]]) -> list[Job]:
        for job in list(self.jobs):
            if job.status not in {"queued", "retry"}:
                continue
            job.status = "running"
            job.started_at = isoformat()
            handler = handlers.get(job.kind)
            try:
                if handler is None:
                    raise RuntimeError(f"No handler for job kind {job.kind}")
                handler(job)
                job.status = "done"
            except Exception as exc:  # noqa: BLE001
                job.status = "failed"
                job.error = str(exc)
            job.finished_at = isoformat()
        return self.jobs

    def monitor(self) -> dict:
        counts: dict[str, int] = {}
        for job in self.jobs:
            counts[job.status] = counts.get(job.status, 0) + 1
        return {
            "total": len(self.jobs),
            "counts": counts,
            "jobs": [
                {"id": j.id, "kind": j.kind, "label": j.label, "status": j.status, "priority": j.priority}
                for j in self.jobs
            ],
        }
