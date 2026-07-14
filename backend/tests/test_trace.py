from app.jobs import JobRepository
from app.trace import sanitize_trace_value


def test_job_starts_with_six_pending_trace_events_in_pipeline_order() -> None:
    job = JobRepository().create("https://www.amazon.com/dp/B0CXT9RSGQ")

    assert [event.stage for event in job.trace_events] == [
        "PRODUCT_FETCH",
        "VISION_ANALYSIS",
        "TEXT_DRAFT",
        "QUALITY_CHECK",
        "TEXT_REVISION",
        "FINALIZE",
    ]
    assert all(event.status == "pending" for event in job.trace_events)


def test_repository_records_trace_lifecycle_and_sanitizes_payloads() -> None:
    repository = JobRepository()
    job = repository.create("https://www.amazon.com/dp/B0CXT9RSGQ")

    repository.start_trace(
        job.id,
        "PRODUCT_FETCH",
        input_data={"asin": "B0CXT9RSGQ", "api_key": "must-not-leak"},
    )
    repository.complete_trace(
        job.id,
        "PRODUCT_FETCH",
        output={"title": "Camping chair", "nested": {"authorization": "Bearer secret"}},
        field_sources={"title": "product.title"},
    )

    event = repository.get(job.id).trace_events[0]  # type: ignore[union-attr]
    assert event.status == "completed"
    assert event.started_at is not None
    assert event.finished_at is not None
    assert event.duration_ms is not None and event.duration_ms >= 0
    assert event.input["api_key"] == "[REDACTED]"
    assert event.output["nested"]["authorization"] == "[REDACTED]"
    assert event.field_sources == {"title": "product.title"}


def test_sanitizer_bounds_text_and_list_size() -> None:
    sanitized = sanitize_trace_value({"value": "x" * 3000, "items": list(range(100))})

    assert len(sanitized["value"]) < 2100
    assert len(sanitized["items"]) == 25

