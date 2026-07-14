import os

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

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


app = FastAPI(title="AI 产品分析助手", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

repository = JobRepository()


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
        raise RuntimeError(f"Live 模式缺少环境变量：{', '.join(missing)}")
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
        repository.update(job_id, status="completed", stage="COMPLETED", progress=100, result=result)
    except Exception as exc:
        repository.update(job_id, status="failed", stage="FAILED", error=sanitize_error(str(exc)))


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
