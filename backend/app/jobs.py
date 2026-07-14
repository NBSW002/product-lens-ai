from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.models import Job


class JobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self, url: str) -> Job:
        job = Job(id=uuid4().hex, url=url)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job_id: str, **changes: object) -> Job:
        with self._lock:
            job = self._jobs[job_id]
            updated = job.model_copy(update={**changes, "updated_at": datetime.now(timezone.utc)})
            self._jobs[job_id] = updated
            return updated

