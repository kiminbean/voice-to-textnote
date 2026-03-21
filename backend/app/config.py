"""
앱 설정 모듈 - pydantic-settings 기반 환경 변수 관리
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
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
    whisper_model: str = "mlx-community/whisper-small-mlx"
    whisper_language: str = "ko"

    # 처리 제한
    # REQ-ERR-007: 범위 유효성 검사 (1-10)
    max_concurrent_jobs: int = Field(default=3, ge=1, le=10)
    # REQ-ERR-007: 범위 유효성 검사 (1-2000 MB)
    max_file_size_mb: int = Field(default=500, ge=1, le=2000)
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
    anthropic_api_key: str = ""  # ANTHROPIC_API_KEY 환경 변수 (미사용 - 호환성 유지)
    openai_api_key: str = ""  # OPENAI_API_KEY 환경 변수
    max_concurrent_summaries: int = 2  # 최대 동시 요약 작업 수
    summary_result_ttl: int = 86400  # 요약 결과 캐시 TTL: 24시간 (초)
    summary_max_tokens: int = 2000  # OpenAI API 최대 응답 토큰
    summary_model: str = "gpt-4o-mini"  # OpenAI 모델명

    # -------------------------------------------------------------------------
    # SPEC-DB-001: 데이터베이스 설정 (REQ-DB-001, REQ-DB-002, REQ-DB-003)
    # -------------------------------------------------------------------------

    # DB 연결 URL (빈 문자열이면 SQLite 폴백 - REQ-DB-002)
    database_url: str = ""

    # 커넥션 풀 최소 크기 (REQ-DB-003)
    db_pool_size: int = 5

    # 커넥션 풀 최대 초과 (pool_size + max_overflow = 최대 연결 수, REQ-DB-003)
    db_max_overflow: int = 15

    # 실행 환경 (development, staging, production)
    environment: str = "development"

    # 로깅
    log_level: str = "INFO"

    # 서버
    host: str = "0.0.0.0"
    port: int = 8000

    # -------------------------------------------------------------------------
    # SPEC-RETENTION-001: 데이터 보존 정책 설정 (REQ-RET-001, REQ-RET-002)
    # -------------------------------------------------------------------------

    # REQ-RET-001: DB 결과 보존 기간 (일, 기본 30일)
    data_retention_days: int = 30

    # REQ-RET-002: 임시 파일 보존 기간 (시간, 기본 24시간)
    temp_file_retention_hours: int = 24

    # -------------------------------------------------------------------------
    # SPEC-SEC-001: 보안 설정 (REQ-SEC-012)
    # -------------------------------------------------------------------------

    # REQ-SEC-001/REQ-SEC-004: API Key 인증
    # 쉼표로 구분된 유효한 API Key 목록 (비어있으면 개발 모드 - 인증 비활성화)
    api_keys: list[str] = []

    # REQ-SEC-007: IP 기반 Rate Limiting (분당 요청 횟수)
    # REQ-ERR-007: 범위 유효성 검사 (1-1000)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)

    # REQ-SEC-009/REQ-SEC-010: CORS 설정
    # 허용할 HTTP 메서드 목록 (와일드카드 금지)
    cors_allow_methods: list[str] = ["GET", "POST", "DELETE"]
    # 허용할 Origins 목록 (기본: 로컬 개발 환경)
    cors_allow_origins: list[str] = ["http://localhost:3000", "http://localhost:8080", "http://localhost:5173"]

    @field_validator("temp_dir", "results_dir", mode="before")
    @classmethod
    def create_dirs(cls, v: str | Path) -> Path:
        path = Path(v)
        # 상대 경로는 프로젝트 루트 기준 절대 경로로 변환 (CWD 의존성 제거)
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parent.parent.parent
            path = project_root / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("api_keys", "cors_allow_methods", "cors_allow_origins", mode="before")
    @classmethod
    def parse_list_from_string(cls, v: str | list) -> list[str]:
        """
        환경 변수에서 쉼표 구분 문자열을 리스트로 파싱
        예: "key1,key2,key3" → ["key1", "key2", "key3"]
        """
        if isinstance(v, str):
            # 빈 문자열이면 빈 리스트 반환
            if not v.strip():
                return []
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

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
