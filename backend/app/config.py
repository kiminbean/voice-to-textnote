"""
앱 설정 모듈 - pydantic-settings 기반 환경 변수 관리
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Redis 설정
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # 파일 저장소
    temp_dir: Path = Path("./storage/temp")
    results_dir: Path = Path("./storage/results")

    # STT 모델
    whisper_model: str = "mlx-community/whisper-large-v3-turbo"
    whisper_language: str = "ko"

    # 처리 제한
    max_concurrent_jobs: int = 3
    max_file_size_mb: int = 500
    max_duration_hours: int = 4
    chunk_duration_minutes: int = 30
    chunk_overlap_seconds: int = 5

    # Redis 캐시 TTL (초)
    cache_ttl_seconds: int = 86400  # 24시간

    # 메모리 경고 임계값 (MB) - 24GB의 80%
    memory_warning_threshold_mb: int = 19660

    # HuggingFace 설정 (화자 분리용)
    huggingface_token: str = ""

    # 화자 분리 설정
    max_concurrent_diarizations: int = 2
    diarization_model: str = "pyannote/speaker-diarization-3.1"
    diarization_result_ttl: int = 86400  # 24시간 (초)

    # 회의록 생성 설정 (REQ-MIN-008, REQ-MIN-013)
    max_concurrent_minutes: int = 3  # 최대 동시 회의록 생성 작업 수
    minutes_result_ttl: int = 86400  # 결과 캐시 TTL: 24시간 (초)

    # AI 요약 생성 설정 (REQ-SUM-008, REQ-SUM-011, REQ-SUM-014)
    anthropic_api_key: str = ""  # ANTHROPIC_API_KEY 환경 변수
    max_concurrent_summaries: int = 2  # 최대 동시 요약 작업 수
    summary_result_ttl: int = 86400  # 요약 결과 캐시 TTL: 24시간 (초)
    summary_max_tokens: int = 2000  # Claude API 최대 응답 토큰
    summary_model: str = "claude-sonnet-4-20250514"  # Claude 모델명

    # 로깅
    log_level: str = "INFO"

    # 서버
    host: str = "0.0.0.0"
    port: int = 8000

    @field_validator("temp_dir", "results_dir", mode="before")
    @classmethod
    def create_dirs(cls, v: str | Path) -> Path:
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024

    @property
    def max_duration_seconds(self) -> int:
        return self.max_duration_hours * 3600

    @property
    def chunk_duration_ms(self) -> int:
        return self.chunk_duration_minutes * 60 * 1000

    @property
    def chunk_overlap_ms(self) -> int:
        return self.chunk_overlap_seconds * 1000


settings = Settings()
