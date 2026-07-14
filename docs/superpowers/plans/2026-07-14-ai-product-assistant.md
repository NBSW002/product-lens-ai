# AI Product Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally runnable React + FastAPI application that analyzes public Amazon product links, enriches them with image understanding, generates Chinese product insights and a short-video script, and reports quality risks.

**Architecture:** A React client creates and polls a staged FastAPI analysis job. The backend normalizes Amazon product data through provider adapters, sends images to Qwen VL, sends structured evidence to DeepSeek V4, and runs deterministic plus model-based quality checks before exposing the final result. In demo mode, the same pipeline uses fixtures so the finished UI works without API keys.

**Tech Stack:** React, TypeScript, Vite, Vitest, FastAPI, Pydantic, pytest, HTTPX, DeepSeek API, Alibaba Cloud Model Studio Qwen VL API.

## Global Constraints

- Accept only public Amazon product URLs and extract the ASIN safely.
- Keep every external API behind an adapter with timeouts and typed errors.
- Never expose API keys to the browser; load them only from backend environment variables.
- Keep product facts separate from model inferences and attach evidence labels.
- The Chinese voice-over must be at most 150 Chinese characters and start with a hook.
- The application must remain fully demonstrable without paid keys through deterministic demo fixtures.
- Do not modify the supplied PDF.

---

### Task 1: Backend domain and URL validation

**Files:**
- Create: `backend/app/models.py`
- Create: `backend/app/url_parser.py`
- Test: `backend/tests/test_url_parser.py`

**Interfaces:**
- Produces: `parse_amazon_url(url: str) -> AmazonLink` and shared Pydantic response models.

- [ ] Write failing tests for `/dp/ASIN`, `/gp/product/ASIN`, encoded product URLs, non-Amazon hosts, and invalid ASINs.
- [ ] Run `pytest backend/tests/test_url_parser.py -v` and confirm failure.
- [ ] Implement strict host allow-listing and ASIN extraction.
- [ ] Re-run the test and confirm all cases pass.

### Task 2: Provider adapters and demo fixtures

**Files:**
- Create: `backend/app/providers/product.py`
- Create: `backend/app/providers/vision.py`
- Create: `backend/app/providers/llm.py`
- Create: `backend/app/fixtures/demo_product.json`
- Test: `backend/tests/test_providers.py`

**Interfaces:**
- Produces: `ProductProvider.fetch(AmazonLink)`, `VisionProvider.analyze(images)`, and `TextModel.analyze(evidence)`.
- Consumes: shared models from Task 1.

- [ ] Write failing adapter contract tests with mocked HTTP responses, timeouts, invalid JSON, and demo mode.
- [ ] Run the tests and confirm failure.
- [ ] Implement demo adapters plus HTTP adapters for a configurable Amazon data provider, Qwen VL, and DeepSeek V4.
- [ ] Re-run tests and confirm adapter normalization and typed errors pass.

### Task 3: Quality gate and staged analysis service

**Files:**
- Create: `backend/app/quality.py`
- Create: `backend/app/service.py`
- Test: `backend/tests/test_quality.py`
- Test: `backend/tests/test_service.py`

**Interfaces:**
- Produces: `QualityChecker.check(...) -> QualityReport` and `AnalysisService.run(job_id, link)`.
- Consumes: provider contracts from Task 2.

- [ ] Write failing tests for unsupported claims, price/spec conflicts, prohibited exaggeration, missing hook, length over 150 characters, progress ordering, and one automatic revision.
- [ ] Run tests and confirm failure.
- [ ] Implement deterministic checks, evidence coverage scoring, progress stages, and one revision pass.
- [ ] Re-run tests and confirm the pipeline passes.

### Task 4: FastAPI job API

**Files:**
- Create: `backend/app/main.py`
- Create: `backend/app/jobs.py`
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Test: `backend/tests/test_api.py`

**Interfaces:**
- Produces: `POST /api/jobs`, `GET /api/jobs/{id}`, `POST /api/jobs/{id}/retry`, and `GET /api/health`.
- Consumes: `AnalysisService` from Task 3.

- [ ] Write failing FastAPI TestClient tests for valid creation, validation errors, progress/result reads, missing jobs, retry, and health.
- [ ] Run tests and confirm failure.
- [ ] Implement an in-memory job repository and background execution suitable for the local assignment demo.
- [ ] Re-run API and full backend tests.

### Task 5: React analysis experience

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/ProgressTimeline.tsx`
- Create: `frontend/src/components/ProductSummary.tsx`
- Create: `frontend/src/components/InsightGrid.tsx`
- Create: `frontend/src/components/ScriptPanel.tsx`
- Create: `frontend/src/components/QualityPanel.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: Task 4 REST API.

- [ ] Write failing component tests for URL submission, staged progress, result sections, copy action, API failure, and retry.
- [ ] Run `npm test -- --run` and confirm failure.
- [ ] Implement the responsive Chinese interface and polling client.
- [ ] Re-run component tests and confirm they pass.

### Task 6: Visual finish, local run, and documentation

**Files:**
- Create: `frontend/src/styles.css`
- Create: `frontend/index.html`
- Create: `README.md`
- Create: `.gitignore`

**Interfaces:**
- Produces: documented local startup and configuration workflow.

- [ ] Add responsive styling, loading/empty/error states, confidence and evidence labels, and accessible controls.
- [ ] Run frontend tests, backend tests, TypeScript build, and a demo-mode API smoke test.
- [ ] Start both services and verify the complete sample analysis in a browser.
- [ ] Document architecture, API variables, demo mode, test commands, deployment options, and known trade-offs.

