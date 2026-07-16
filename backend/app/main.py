'''
import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.history import build_history_store_from_env
from app.jobs import JobRepository, new_trace_events
from app.models import CreateJobRequest, Job, TraceStage
from app.providers import (
    DeepSeekTextModel,
    DemoProductProvider,
    DemoTextModel,
    DemoVisionProvider,
    QwenVisionProvider,
    RainforestProductProvider,
)
from app.service import AnalysisService
from app.trace import sanitize_error
from app.url_parser import InvalidAmazonUrl, parse_amazon_url


logger = logging.getLogger(__name__)


app = FastAPI(title="AI 产品分析助手", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = JobRepository()
history_store = build_history_store_from_env()


def persist_job_history(job: Job) -> None:
    if history_store is None:
        return
            """

    try:
        history_store.save_job(job)
    except Exception as exc:
        logger.exception("Failed to persist job history")
        if job.status == "completed":
            repository.update(job.id, error=f"历史记录保存失败: {sanitize_error(str(exc))}")


def build_service() -> AnalysisService:
    if os.getenv("APP_MODE", "demo") != "live":
        return AnalysisService(DemoProductProvider(), DemoVisionProvider(), DemoTextModel())
    required = {
        "RAINFOREST_API_KEY": os.getenv("RAINFOREST_API_KEY"),
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Live 模式缺少环境变量: {', '.join(missing)}")
        """
        raise RuntimeError(f"Live 模式缺少环境变量：{', '.join(missing)}")
        """
    return AnalysisService(
        RainforestProductProvider(required["RAINFOREST_API_KEY"] or ""),
        QwenVisionProvider(required["DASHSCOPE_API_KEY"] or ""),
        DeepSeekTextModel(required["DEEPSEEK_API_KEY"] or ""),
    )


service = build_service()


def run_job(job_id: str) -> None:
    job = repository.get(job_id)
    if not job:
        return
    repository.update(job_id, status="running")

    def record_trace(action: str, stage: TraceStage, payload: dict[str, object]) -> None:
        if action == "start":
            input_data = payload.get("input")
            repository.start_trace(job_id, stage, input_data=input_data if isinstance(input_data, dict) else {})
        elif action == "complete":
            output = payload.get("output")
            field_sources = payload.get("field_sources")
            repository.complete_trace(
                job_id,
                stage,
                output=output if isinstance(output, dict) else {},
                field_sources=field_sources if isinstance(field_sources, dict) else {},
            )
        elif action == "fail":
            repository.fail_trace(job_id, stage, str(payload.get("error") or "阶段执行失败"))
        elif action == "skip":
            repository.skip_trace(job_id, stage, str(payload.get("reason") or "已跳过"))
            """
            repository.skip_trace(job_id, stage, str(payload.get("reason") or "已跳过"))

    try:
        result = service.run(
            job.url,
            on_progress=lambda stage, progress: repository.update(job_id, stage=stage, progress=progress),
            on_trace=record_trace,
        )
        completed_job = repository.update(job_id, status="completed", stage="COMPLETED", progress=100, result=result)
        persist_job_history(completed_job)
    except Exception as exc:
        failed_job = repository.update(job_id, status="failed", stage="FAILED", error=sanitize_error(str(exc)))
        persist_job_history(failed_job)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": os.getenv("APP_MODE", "demo")}


@app.post("/api/jobs", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateJobRequest, background_tasks: BackgroundTasks) -> Job:
    try:
        parse_amazon_url(payload.url)
    except InvalidAmazonUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = repository.create(payload.url)
    background_tasks.add_task(run_job, job.id)
    return job


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@app.post("/api/jobs/{job_id}/retry", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, background_tasks: BackgroundTasks) -> Job:
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in {"queued", "running"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务仍在运行，不能重复启动")
    updated = repository.update(
        job_id,
        status="queued",
        stage="QUEUED",
        progress=0,
        error=None,
        result=None,
        trace_events=new_trace_events(),
    )
    background_tasks.add_task(run_job, job_id)
    return updated
'''

import logging
import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.history import build_history_store_from_env
from app.jobs import JobRepository, new_trace_events
from app.models import CreateJobRequest, Job, TraceStage
from app.providers import (
    DeepSeekTextModel,
    DemoProductProvider,
    DemoTextModel,
    DemoVisionProvider,
    QwenVisionProvider,
    RainforestProductProvider,
)
from app.service import AnalysisService
from app.trace import sanitize_error
from app.url_parser import InvalidAmazonUrl, parse_amazon_url


logger = logging.getLogger(__name__)

app = FastAPI(title="AI 商品分析助手", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = JobRepository()
history_store = build_history_store_from_env()


def persist_job_history(job: Job) -> None:
    if history_store is None:
        return
    try:
        history_store.save_job(job)
    except Exception as exc:
        logger.exception("Failed to persist job history")
        if job.status == "completed":
            repository.update(job.id, error=f"历史记录保存失败: {sanitize_error(str(exc))}")


def build_service() -> AnalysisService:
    if os.getenv("APP_MODE", "demo") != "live":
        return AnalysisService(DemoProductProvider(), DemoVisionProvider(), DemoTextModel())
    required = {
        "RAINFOREST_API_KEY": os.getenv("RAINFOREST_API_KEY"),
        "DASHSCOPE_API_KEY": os.getenv("DASHSCOPE_API_KEY"),
        "DEEPSEEK_API_KEY": os.getenv("DEEPSEEK_API_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Live 模式缺少环境变量: {', '.join(missing)}")
    return AnalysisService(
        RainforestProductProvider(required["RAINFOREST_API_KEY"] or ""),
        QwenVisionProvider(required["DASHSCOPE_API_KEY"] or ""),
        DeepSeekTextModel(required["DEEPSEEK_API_KEY"] or ""),
    )


service = build_service()


def run_job(job_id: str) -> None:
    job = repository.get(job_id)
    if not job:
        return
    repository.update(job_id, status="running")

    def record_trace(action: str, stage: TraceStage, payload: dict[str, object]) -> None:
        if action == "start":
            input_data = payload.get("input")
            repository.start_trace(job_id, stage, input_data=input_data if isinstance(input_data, dict) else {})
        elif action == "complete":
            output = payload.get("output")
            field_sources = payload.get("field_sources")
            repository.complete_trace(
                job_id,
                stage,
                output=output if isinstance(output, dict) else {},
                field_sources=field_sources if isinstance(field_sources, dict) else {},
            )
        elif action == "fail":
            repository.fail_trace(job_id, stage, str(payload.get("error") or "阶段执行失败"))
        elif action == "skip":
            repository.skip_trace(job_id, stage, str(payload.get("reason") or "已跳过"))

    try:
        result = service.run(
            job.url,
            on_progress=lambda stage, progress: repository.update(job_id, stage=stage, progress=progress),
            on_trace=record_trace,
        )
        completed_job = repository.update(job_id, status="completed", stage="COMPLETED", progress=100, result=result)
        persist_job_history(completed_job)
    except Exception as exc:
        failed_job = repository.update(job_id, status="failed", stage="FAILED", error=sanitize_error(str(exc)))
        persist_job_history(failed_job)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": os.getenv("APP_MODE", "demo")}


@app.post("/api/jobs", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: CreateJobRequest, background_tasks: BackgroundTasks) -> Job:
    try:
        parse_amazon_url(payload.url)
    except InvalidAmazonUrl as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    job = repository.create(payload.url)
    background_tasks.add_task(run_job, job.id)
    return job


@app.get("/api/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


@app.post("/api/jobs/{job_id}/retry", response_model=Job, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, background_tasks: BackgroundTasks) -> Job:
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="任务不存在")
    if job.status in {"queued", "running"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务仍在运行，不能重复启动")
    updated = repository.update(
        job_id,
        status="queued",
        stage="QUEUED",
        progress=0,
        error=None,
        result=None,
        trace_events=new_trace_events(),
    )
    background_tasks.add_task(run_job, job_id)
    return updated


# Authenticated application wiring. This final app definition is the one exported
# by uvicorn because it is assigned after the legacy implementation above.
import logging as _logging
import os as _os

from fastapi import BackgroundTasks as _BackgroundTasks
from fastapi import Depends, Header, HTTPException as _HTTPException, Request, status as _status
from fastapi import FastAPI as _FastAPI
from fastapi.middleware.cors import CORSMiddleware as _CORSMiddleware

from app.auth import (
    AuthResponse,
    DuplicateUserError,
    InsufficientPointsError,
    InvalidCredentialsError,
    LedgerEntry,
    LoginRequest,
    PointsResponse,
    RegisterRequest,
    UserPublic,
    build_auth_store_from_env,
)
from app.history import build_history_store_from_env as _build_history_store_from_env
from app.jobs import JobRepository as _JobRepository
from app.jobs import new_trace_events as _new_trace_events
from app.models import CreateJobRequest as _CreateJobRequest
from app.models import Job as _Job
from app.models import TraceStage as _TraceStage
from app.providers import (
    DeepSeekTextModel as _DeepSeekTextModel,
    DemoProductProvider as _DemoProductProvider,
    DemoTextModel as _DemoTextModel,
    DemoVisionProvider as _DemoVisionProvider,
    QwenVisionProvider as _QwenVisionProvider,
    RainforestProductProvider as _RainforestProductProvider,
)
from app.service import AnalysisService as _AnalysisService
from app.trace import sanitize_error as _sanitize_error
from app.url_parser import InvalidAmazonUrl as _InvalidAmazonUrl
from app.url_parser import parse_amazon_url as _parse_amazon_url


logger = _logging.getLogger(__name__)
app = _FastAPI(title="AI Product Analysis Assistant", version="0.2.0")
app.add_middleware(
    _CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = _JobRepository()
history_store = _build_history_store_from_env()
auth_store = build_auth_store_from_env()


def _build_service() -> _AnalysisService:
    if _os.getenv("APP_MODE", "demo") != "live":
        return _AnalysisService(_DemoProductProvider(), _DemoVisionProvider(), _DemoTextModel())
    required = {
        "RAINFOREST_API_KEY": _os.getenv("RAINFOREST_API_KEY"),
        "DASHSCOPE_API_KEY": _os.getenv("DASHSCOPE_API_KEY"),
        "DEEPSEEK_API_KEY": _os.getenv("DEEPSEEK_API_KEY"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise RuntimeError(f"Live mode missing environment variables: {', '.join(missing)}")
    return _AnalysisService(
        _RainforestProductProvider(required["RAINFOREST_API_KEY"] or ""),
        _QwenVisionProvider(required["DASHSCOPE_API_KEY"] or ""),
        _DeepSeekTextModel(required["DEEPSEEK_API_KEY"] or ""),
    )


service = _build_service()


def _require_auth_store():
    if auth_store is None:
        raise _HTTPException(status_code=503, detail="User database is not configured")
    return auth_store


def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise _HTTPException(status_code=401, detail="Login required")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise _HTTPException(status_code=401, detail="Login required")
    return token


def current_user(token: str = Depends(_bearer_token)) -> UserPublic:
    store = _require_auth_store()
    user = store.authenticate(token)
    if user is None:
        raise _HTTPException(status_code=401, detail="Invalid or expired login")
    return user


def _persist_job_history(job: _Job) -> None:
    if history_store is None:
        return
    try:
        history_store.save_job(job)
    except Exception as exc:
        logger.exception("Failed to persist job history")
        if job.status == "completed":
            repository.update(job.id, error=f"History save failed: {_sanitize_error(str(exc))}")


def _run_job(job_id: str) -> None:
    job = repository.get(job_id)
    if not job:
        return
    repository.update(job_id, status="running")

    def record_trace(action: str, stage: _TraceStage, payload: dict[str, object]) -> None:
        if action == "start":
            input_data = payload.get("input")
            repository.start_trace(job_id, stage, input_data=input_data if isinstance(input_data, dict) else {})
        elif action == "complete":
            output = payload.get("output")
            field_sources = payload.get("field_sources")
            repository.complete_trace(
                job_id,
                stage,
                output=output if isinstance(output, dict) else {},
                field_sources=field_sources if isinstance(field_sources, dict) else {},
            )
        elif action == "fail":
            repository.fail_trace(job_id, stage, str(payload.get("error") or "Stage failed"))
        elif action == "skip":
            repository.skip_trace(job_id, stage, str(payload.get("reason") or "Skipped"))

    try:
        result = service.run(
            job.url,
            on_progress=lambda stage, progress: repository.update(job_id, stage=stage, progress=progress),
            on_trace=record_trace,
        )
        completed_job = repository.update(job_id, status="completed", stage="COMPLETED", progress=100, result=result)
        _persist_job_history(completed_job)
    except Exception as exc:
        failed_job = repository.update(job_id, status="failed", stage="FAILED", error=_sanitize_error(str(exc)))
        if auth_store is not None:
            try:
                auth_store.refund_analysis_point(job_id)
            except Exception:
                logger.exception("Failed to refund point for failed job")
        _persist_job_history(failed_job)


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "mode": _os.getenv("APP_MODE", "demo"),
        "auth": auth_store is not None,
        "history": history_store is not None,
    }


@app.post("/api/auth/register", response_model=AuthResponse, status_code=_status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request) -> AuthResponse:
    if "@" not in payload.email:
        raise _HTTPException(status_code=422, detail="Invalid email")
    store = _require_auth_store()
    try:
        return store.register(
            payload,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except DuplicateUserError as exc:
        raise _HTTPException(status_code=409, detail="Email already registered") from exc


@app.post("/api/auth/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request) -> AuthResponse:
    store = _require_auth_store()
    try:
        return store.login(
            payload,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as exc:
        raise _HTTPException(status_code=401, detail="Invalid email or password") from exc


@app.post("/api/auth/logout", status_code=_status.HTTP_204_NO_CONTENT)
def logout(token: str = Depends(_bearer_token)) -> None:
    store = _require_auth_store()
    store.logout(token)


@app.get("/api/me", response_model=UserPublic)
def me(user: UserPublic = Depends(current_user)) -> UserPublic:
    return user


@app.get("/api/points", response_model=PointsResponse)
def points(user: UserPublic = Depends(current_user)) -> PointsResponse:
    store = _require_auth_store()
    return store.get_points(user.id)


@app.get("/api/points/ledger", response_model=list[LedgerEntry])
def points_ledger(user: UserPublic = Depends(current_user)) -> list[LedgerEntry]:
    store = _require_auth_store()
    return store.get_ledger(user.id)


@app.post("/api/jobs", response_model=_Job, status_code=_status.HTTP_202_ACCEPTED)
def create_job(
    payload: _CreateJobRequest,
    background_tasks: _BackgroundTasks,
    user: UserPublic = Depends(current_user),
) -> _Job:
    try:
        _parse_amazon_url(payload.url)
    except _InvalidAmazonUrl as exc:
        raise _HTTPException(status_code=422, detail=str(exc)) from exc
    store = _require_auth_store()
    job = repository.create(payload.url)
    try:
        store.reserve_analysis_point(user.id, job)
    except InsufficientPointsError as exc:
        raise _HTTPException(status_code=402, detail="Insufficient points") from exc
    background_tasks.add_task(_run_job, job.id)
    return job


@app.get("/api/jobs/{job_id}", response_model=_Job)
def get_job(job_id: str, user: UserPublic = Depends(current_user)) -> _Job:
    store = _require_auth_store()
    if not store.user_owns_job(user, job_id):
        raise _HTTPException(status_code=404, detail="Job not found")
    job = repository.get(job_id)
    if not job:
        raise _HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/jobs/{job_id}/retry", response_model=_Job, status_code=_status.HTTP_202_ACCEPTED)
def retry_job(
    job_id: str,
    background_tasks: _BackgroundTasks,
    user: UserPublic = Depends(current_user),
) -> _Job:
    store = _require_auth_store()
    if not store.user_owns_job(user, job_id):
        raise _HTTPException(status_code=404, detail="Job not found")
    job = repository.get(job_id)
    if not job:
        raise _HTTPException(status_code=404, detail="Job not found")
    if job.status in {"queued", "running"}:
        raise _HTTPException(status_code=_status.HTTP_409_CONFLICT, detail="Job is still running")
    updated = repository.update(
        job_id,
        status="queued",
        stage="QUEUED",
        progress=0,
        error=None,
        result=None,
        trace_events=_new_trace_events(),
    )
    try:
        store.reserve_analysis_point(user.id, updated)
    except InsufficientPointsError as exc:
        raise _HTTPException(status_code=402, detail="Insufficient points") from exc
    background_tasks.add_task(_run_job, job_id)
    return updated
