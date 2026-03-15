"""
헬스체크 응답 Pydantic v2 스키마
REQ-STT-019, REQ-STT-020 관련
"""
from datetime import datetime

from pydantic import BaseModel


class CeleryWorkersStatus(BaseModel):
    status: str
    active_workers: int
    active_tasks: int


class HealthComponents(BaseModel):
    api: str
    redis: str
    celery_workers: CeleryWorkersStatus
    ffmpeg: str


class HealthResponse(BaseModel):
    """GET /api/v1/health 응답"""
    status: str
    version: str
    components: HealthComponents
    timestamp: datetime


class ModelStatusResponse(BaseModel):
    """GET /api/v1/health/model 응답"""
    model_name: str
    model_loaded: bool
    device: str | None = None
    memory_usage_mb: float | None = None
    total_system_memory_mb: float | None = None
    available_memory_mb: float | None = None
    load_time_seconds: float | None = None
    version: str | None = None
