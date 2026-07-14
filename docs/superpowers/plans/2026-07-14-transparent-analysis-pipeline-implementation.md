# Transparent Analysis Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a secure, in-memory, six-stage audit trail to every analysis job and reject empty or ungrounded model output instead of presenting it as a successful 88-point result.

**Architecture:** Extend the existing Pydantic job model and thread-safe repository with trace events, then make `AnalysisService` emit explicit start/complete/fail/skip events around each provider boundary. Keep provider responses normalized, expose only explicitly constructed evidence, and render the trace from the existing polling API with accessible expandable React components.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, httpx, pytest, React 19, TypeScript, Vitest, Testing Library, Vite.

## Global Constraints

- Trace storage remains in memory and is cleared on backend restart.
- Never store or return API keys, Authorization headers, tokens, secrets, or passwords.
- Preserve DeepSeek draft and revision as separate events.
- Do not save the full third-party raw response.
- Keep the existing polling transport; do not add WebSocket or a database.
- The directory is not a valid Git repository, so commit steps are intentionally omitted.

---

### Task 1: Trace models, sanitization, and repository lifecycle

**Files:**
- Modify: `backend/app/models.py`
- Modify: `backend/app/jobs.py`
- Create: `backend/app/trace.py`
- Create: `backend/tests/test_trace.py`

**Interfaces:**
- Produces `TraceEvent`, `TraceStage`, `TraceStatus` in `app.models`.
- Produces `sanitize_trace_value(value: object) -> object` in `app.trace`.
- Produces `JobRepository.start_trace(...)`, `complete_trace(...)`, `fail_trace(...)`, and `skip_trace(...)`.

- [ ] Write failing tests proving six pending events are created in order, lifecycle timestamps and duration are populated, and nested sensitive keys are replaced with `[REDACTED]`.
- [ ] Run `uv run pytest backend/tests/test_trace.py -q` from the repository root and confirm failures are caused by missing trace APIs.
- [ ] Add the trace Pydantic types, `trace_events: list[TraceEvent]`, bounded recursive sanitizer, and locked repository event replacement.
- [ ] Re-run the focused tests and confirm they pass.

The event skeleton is:

```python
class TraceEvent(BaseModel):
    id: str
    stage: TraceStage
    title: str
    status: TraceStatus = "pending"
    provider: str
    model: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    input: dict[str, object] = Field(default_factory=dict)
    output: dict[str, object] = Field(default_factory=dict)
    field_sources: dict[str, str] = Field(default_factory=dict)
    error: str | None = None
```

### Task 2: Quality completeness rules

**Files:**
- Modify: `backend/tests/test_quality.py`
- Modify: `backend/app/quality.py`

**Interfaces:**
- `QualityChecker.check(ProductFacts, ProductAnalysis) -> QualityReport` remains stable.
- Adds `EMPTY_*` high-severity issue codes and a zero-score rule for fully empty analyses.

- [ ] Add failing tests for an all-empty `ProductAnalysis` and individually empty core fields.
- [ ] Verify the all-empty case currently returns 88 and the new test fails for that exact reason.
- [ ] Add high-severity completeness issues before claim checking; set score to zero when all six content areas are empty; require positive evidence coverage to pass.
- [ ] Re-run `uv run pytest backend/tests/test_quality.py -q` and confirm all quality tests pass.

Required pass condition:

```python
passed = (
    score >= 80
    and coverage > 0
    and not any(issue.severity == "high" for issue in issues)
)
```

### Task 3: Provider normalization and content validation

**Files:**
- Modify: `backend/tests/test_live_providers.py`
- Modify: `backend/app/providers/live.py`

**Interfaces:**
- `RainforestProductProvider.fetch` continues returning `ProductFacts`.
- Providers expose `provider_name`, optional `model`, and a static field-source map for trace construction.
- Qwen and DeepSeek reject structurally valid but empty content with `ProviderError`.

- [ ] Add failing tests for a mismatched Rainforest ASIN, malformed array/spec fields, empty Qwen findings, and empty DeepSeek fields.
- [ ] Verify each test fails because the invalid payload is currently accepted.
- [ ] Validate returned ASIN when present, normalize only expected list/dict shapes, and add the field-source map.
- [ ] Reject empty Qwen findings and DeepSeek analyses with a safe provider error.
- [ ] Run `uv run pytest backend/tests/test_live_providers.py -q` and confirm passing results.

No raw request, headers, API key, or unbounded provider payload may be returned by these interfaces.

### Task 4: Service orchestration and auditable failure behavior

**Files:**
- Modify: `backend/tests/test_service.py`
- Modify: `backend/app/service.py`
- Modify: `backend/app/main.py`

**Interfaces:**
- Add `TraceCallback = Callable[[str, str, dict[str, object]], None]` or an equivalent typed event callback.
- `AnalysisService.run` accepts `on_trace` alongside the existing progress callback.
- `run_job` maps service events into repository lifecycle methods.

- [ ] Add failing service tests asserting the six-stage order, separate draft/revision outputs, skipped revision on first-pass quality, and failure propagation without deleting completed events.
- [ ] Verify focused tests fail because no trace callback exists.
- [ ] Emit explicit boundary events around product fetch, vision, draft, quality, revision, and finalization.
- [ ] On an exception, fail the active stage and mark later pending stages skipped before marking the job failed.
- [ ] Reset traces when retrying a job.
- [ ] Run backend service and API tests and confirm all pass.

The finalization rule is strict: an `AnalysisResult` is returned only when the final `QualityReport.passed` is true; otherwise raise a safe error after recording the report.

### Task 5: Frontend trace contract and mode API

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/AnalysisTrace.tsx`
- Create: `frontend/src/components/TraceStep.tsx`
- Create: `frontend/src/components/AnalysisTrace.test.tsx`

**Interfaces:**
- Add `TraceEvent` and `HealthStatus` TypeScript interfaces matching backend JSON.
- Add `getHealth(): Promise<HealthStatus>`.
- `AnalysisTrace` accepts `{ events: TraceEvent[] }`.

- [ ] Write failing component tests for fixed ordering, accessible expansion, structured input/output, field sources, failure text, and skipped reasons.
- [ ] Run `npm test -- --run src/components/AnalysisTrace.test.tsx` from `frontend` and confirm failure due to missing components.
- [ ] Implement semantic timeline markup with `button`, `aria-expanded`, status text, `<pre>` JSON blocks, and no HTML injection.
- [ ] Re-run the focused frontend test and confirm passing results.

### Task 6: Integrate live trace and dynamic mode into the application

**Files:**
- Modify: `frontend/src/App.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**Interfaces:**
- `App` loads `/api/health` once and renders “真实 API” or “演示模式”.
- Every non-null job renders `AnalysisTrace` before final results.

- [ ] Extend the App fixture with trace events and add failing tests for dynamic mode, trace visibility while running, and failed jobs that retain trace but do not render empty result cards.
- [ ] Verify failures are caused by the hard-coded badge and absent trace UI.
- [ ] Fetch health on mount, replace the hard-coded badge, render `AnalysisTrace`, and keep the result section gated on successful `job.result`.
- [ ] Add responsive timeline/accordion styles consistent with the existing green visual system.
- [ ] Run the focused App tests and confirm passing results.

### Task 7: Full regression and local browser verification

**Files:**
- Modify: `README.md` only if startup or behavior documentation is now inaccurate.

**Interfaces:**
- No new interfaces.

- [ ] Run `uv run pytest -q` from `backend` and require all backend tests to pass.
- [ ] Run `npm test -- --run` from `frontend` and require all frontend tests to pass.
- [ ] Run `npm run build` from `frontend` and require TypeScript/Vite build success.
- [ ] Start backend in Demo mode on an available port and frontend on an available port without using live keys.
- [ ] Use the in-app browser to verify the six steps, expansion content, dynamic Demo badge, and final grounded result.
- [ ] Stop verification processes and report exact commands and results.

