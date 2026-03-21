"""
헬스체크 응답 Pydantic v2 스키마
REQ-STT-019, REQ-STT-020 관련
REQ-LIFE-006: 버전 정보, 시작 시각, 업타임 필드 추가
"""

from datetime import datetime
from typing import Optional

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
    # REQ-LIFE-006: 앱 시작 시각 (UTC ISO 8601 형식, 미시작 시 None)
    started_at: Optional[str] = None
    # REQ-LIFE-006: 서버 업타임 (초, 미시작 시 0)
    uptime_seconds: float = 0

    model_config = {"populate_by_name": True}


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


class DiarizationModelStatusResponse(BaseModel):
    """GET /api/v1/health/diarization 응답"""

    model_config = {"protected_namespaces": ()}

    model_name: str
    model_loaded: bool
    load_time_seconds: float | None = None
