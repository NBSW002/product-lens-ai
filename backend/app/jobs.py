from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4

from app.models import Job, TraceEvent, TraceStage
from app.trace import sanitize_trace_value


TRACE_DEFINITIONS: tuple[tuple[TraceStage, str, str, str | None], ...] = (
    ("PRODUCT_FETCH", "商品抓取", "Rainforest", None),
    ("VISION_ANALYSIS", "图片分析", "Qwen", "qwen3-vl-plus"),
    ("TEXT_DRAFT", "DeepSeek 初稿", "DeepSeek", "deepseek-v4-flash"),
    ("QUALITY_CHECK", "质量检查", "Internal", None),
    ("TEXT_REVISION", "自动修订", "DeepSeek", "deepseek-v4-flash"),
    ("FINALIZE", "最终结果", "Internal", None),
)


def new_trace_events() -> list[TraceEvent]:
    return [
        TraceEvent(id=stage.lower(), stage=stage, title=title, provider=provider, model=model)
        for stage, title, provider, model in TRACE_DEFINITIONS
    ]


class JobRepository:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = Lock()

    def create(self, url: str) -> Job:
        job = Job(id=uuid4().hex, url=url, trace_events=new_trace_events())
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

    def _update_trace(self, job_id: str, stage: TraceStage, **changes: object) -> Job:
        with self._lock:
            job = self._jobs[job_id]
            events = [
                event.model_copy(update=changes) if event.stage == stage else event
                for event in job.trace_events
            ]
            updated = job.model_copy(update={"trace_events": events, "updated_at": datetime.now(timezone.utc)})
            self._jobs[job_id] = updated
            return updated

    def start_trace(self, job_id: str, stage: TraceStage, input_data: dict[str, object] | None = None) -> Job:
        return self._update_trace(
            job_id,
            stage,
            status="running",
            started_at=datetime.now(timezone.utc),
            input=sanitize_trace_value(input_data or {}),
            error=None,
        )

    def complete_trace(
        self,
        job_id: str,
        stage: TraceStage,
        output: dict[str, object] | None = None,
        field_sources: dict[str, str] | None = None,
    ) -> Job:
        job = self.get(job_id)
        event = next(item for item in job.trace_events if item.stage == stage)  # type: ignore[union-attr]
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - (event.started_at or finished_at)).total_seconds() * 1000)
        return self._update_trace(
            job_id,
            stage,
            status="completed",
            finished_at=finished_at,
            duration_ms=max(0, duration_ms),
            output=sanitize_trace_value(output or {}),
            field_sources=field_sources or {},
        )

    def fail_trace(self, job_id: str, stage: TraceStage, error: str) -> Job:
        job = self.get(job_id)
        event = next(item for item in job.trace_events if item.stage == stage)  # type: ignore[union-attr]
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((finished_at - (event.started_at or finished_at)).total_seconds() * 1000)
        return self._update_trace(
            job_id,
            stage,
            status="failed",
            finished_at=finished_at,
            duration_ms=max(0, duration_ms),
            error=error,
        )

    def skip_trace(self, job_id: str, stage: TraceStage, reason: str) -> Job:
        now = datetime.now(timezone.utc)
        return self._update_trace(
            job_id,
            stage,
            status="skipped",
            started_at=now,
            finished_at=now,
            duration_ms=0,
            error=reason,
        )
