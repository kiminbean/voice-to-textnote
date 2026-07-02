"""
앱 설정 모듈 - pydantic-settings 기반 환경 변수 관리
"""

from pathlib import Path
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}
_DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:8080",
    "http://localhost:5173",
]
_ZAI_CODING_PLAN_BASE_URL = "https://api.z.ai/api/coding/paas/v4"


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
    # REQ-TMPL-001: 양식 파일 저장소
    templates_dir: Path = Path("./storage/templates")

    # STT 모델
    whisper_model: str = "mlx-community/whisper-small-mlx"
    whisper_language: str = "ko"
    stt_backend: str = ""  # "mlx", "faster_whisper", "" (auto-detect)
    preload_models_enabled: bool = Field(
        default=True,
        validation_alias=AliasChoices("PRELOAD_MODELS_ENABLED", "MODEL_PRELOAD_ENABLED"),
    )

    # 처리 제한
    # REQ-ERR-007: 범위 유효성 검사 (1-10)
    max_concurrent_jobs: int = Field(default=3, ge=1, le=10)
    # REQ-ERR-007: 범위 유효성 검사 (1-2000 MB)
    max_file_size_mb: int = Field(default=500, ge=1, le=2000)
    max_duration_hours: int = 4
    chunk_duration_minutes: int = 30
    chunk_overlap_seconds: int = 5

    # Redis 캐시 TTL (초)
    cache_ttl_seconds: int = 604800  # 7일

    # 메모리 경고 임계값 (MB) - 24GB의 80%
    memory_warning_threshold_mb: int = 19660

    # HuggingFace 설정 (화자 분리용)
    huggingface_token: str = ""

    # 화자 분리 설정
    max_concurrent_diarizations: int = 2
    diarization_model: str = "pyannote/speaker-diarization-community-1"
    diarization_fallback_model: str = "pyannote/speaker-diarization-3.1"
    default_diarization_max_speakers: int = Field(default=10, ge=1, le=50)
    diarization_result_ttl: int = 604800  # 7일 (초)
    # REQ-PERF-001: 화자 분리 청크 분할 설정
    dia_chunk_duration_minutes: int = 10  # 청크 단위 (분)
    dia_chunk_overlap_seconds: int = 30  # 청크 간 오버랩 (초)
    dia_chunk_threshold_minutes: int = 15  # 이 길이 이상이면 청크 분할 적용
    # REQ-DIA-PERF-003: 다운샘플링 (실험적, 정확도 손실 위험으로 default 비활성)
    # 0 또는 음수면 비활성. 8000 등으로 설정하면 pyannote 입력 전 resample.
    # pyannote 3.1은 16kHz로 학습됐으므로 다운샘플링 시 정확도 영향 가능.
    dia_target_sample_rate: int = 0

    # Voiceprint speaker identification.
    speaker_embedding_model: str = "pyannote/embedding"
    speaker_voiceprint_similarity_threshold: float = Field(default=0.82, ge=0.0, le=1.0)
    speaker_voiceprint_max_seconds_per_speaker: float = Field(default=30.0, ge=1.0, le=300.0)
    speaker_voiceprint_min_match_seconds: float = Field(default=8.0, ge=0.2, le=120.0)
    speaker_voiceprint_min_enroll_seconds: float = Field(default=8.0, ge=0.2, le=120.0)

    # 회의록 생성 설정 (REQ-MIN-008, REQ-MIN-013)
    max_concurrent_minutes: int = 3  # 최대 동시 회의록 생성 작업 수
    minutes_result_ttl: int = 604800  # 결과 캐시 TTL: 7일 (초)

    # AI 요약 생성 설정 (REQ-SUM-008, REQ-SUM-011, REQ-SUM-014)
    # Z.AI Coding Plan is the default LLM provider.
    llm_provider: str = "zai"
    anthropic_api_key: str = ""  # ANTHROPIC_API_KEY 환경 변수 (미사용 - 호환성 유지)
    zai_api_key: str = ""  # ZAI_API_KEY 환경 변수
    zai_base_url: str = ""  # ZAI_BASE_URL 환경 변수
    max_concurrent_summaries: int = 2  # 최대 동시 요약 작업 수
    summary_result_ttl: int = 604800  # 요약 결과 캐시 TTL: 7일 (초)
    # 양식 섹션 포함 시 4000+ 토큰 필요 (9개 섹션 + action_items + key_decisions)
    summary_max_tokens: int = 4096  # ZAI API 최대 응답 토큰
    summary_model: str = "glm-5.2"  # ZAI 모델명

    # SPEC-SENTIMENT-001: 감정 분석 동시 실행 제한 (REQ-SEN-004)
    # 기존 MAX_CONCURRENT_SENTIMENT=3 하드코딩에서 설정 이관
    max_concurrent_sentiment: int = Field(default=3, ge=1, le=10)

    # SPEC-TONE-001: 발화 톤/운율 분석 설정 (REQ-TONE-001, REQ-TONE-011)
    # REQ-TONE-011: 빈 문자열이면 tone 기능 전체 비활성화 (API 503, Celery 미트리거)
    tone_model: str = ""
    tone_result_ttl: int = 86400  # 24시간 Redis 캐시 TTL (초)
    max_concurrent_tone: int = 1  # 메모리 보호를 위한 동시 실행 제한
    # REQ-TONE-002: 이 길이 미만 세그먼트는 F0/RMS 추출 불안정으로 분석 스킵
    tone_min_segment_duration_sec: float = 0.5

    # -------------------------------------------------------------------------
    # SPEC-DB-001: 데이터베이스 설정 (REQ-DB-001, REQ-DB-002, REQ-DB-003)
    # -------------------------------------------------------------------------

    # DB 연결 URL (빈 문자열이면 SQLite 폴백 - REQ-DB-002)
    database_url: str = ""

    # 커넥션 풀 최소 크기 (REQ-DB-003)
    db_pool_size: int = Field(default=5, ge=1, le=100)

    # 커넥션 풀 최대 초과 (pool_size + max_overflow = 최대 연결 수, REQ-DB-003)
    db_max_overflow: int = Field(default=15, ge=0, le=100)

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

    # SPEC-TEAM-001: JWT 시크릿 키 (access token 서명용)
    # 프로덕션에서는 반드시 환경 변수로 강력한 키 설정 필요
    jwt_secret: str = "dev-insecure-change-me"

    # SPEC-GUEST-001: 게스트 세션 TTL (시간)
    guest_session_ttl_hours: int = Field(default=24, ge=1, le=168)

    # REQ-OAUTH-001: Google OAuth 설정
    google_client_id: str = ""

    # REQ-OAUTH-001: Apple Sign-In 설정
    apple_team_id: str = ""
    apple_client_id: str = ""
    apple_key_id: str = ""

    # REQ-SEC-001/REQ-SEC-004: API Key 인증
    # 쉼표로 구분된 유효한 API Key 목록 (비어있으면 개발 모드 - 인증 비활성화)
    api_keys: list[str] | str = Field(default_factory=lambda: [])

    # REQ-SEC-007: IP 기반 Rate Limiting (분당 요청 횟수)
    # REQ-ERR-007: 범위 유효성 검사 (1-1000)
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)

    # -------------------------------------------------------------------------
    # SPEC-MOBILE-004: Firebase Push 알림 설정 (REQ-MOBILE-002-06)
    # -------------------------------------------------------------------------
    # Firebase 서비스 계정 키 JSON 파일 경로 (미설정 시 MOCK 모드)
    firebase_credentials_path: str | None = None

    # SPEC-BOOKMARK-001: 회의록 북마크/하이라이트 설정
    # 한 회의록당 최대 북마크 수 (무분별한 생성 방지)
    bookmark_max_per_meeting: int = Field(default=200, ge=1, le=10000)
    # 북마크 노트 최대 길이 (문자)
    bookmark_note_max_length: int = Field(default=2000, ge=1, le=20000)

    # SPEC-AUDIO-PREP-001: 오디오 전처리 API 설정
    # 전처리 엔드포인트 활성화 여부 (운영에서 비활성화하려면 false)
    audio_preprocess_enabled: bool = True
    # 전처리에 허용되는 최대 업로드 크기 (MB). 메인 max_file_size_mb와 별도.
    audio_preprocess_max_file_mb: int = Field(default=200, ge=1, le=2000)
    # 전처리 동시 실행 제한 (서버 CPU 보호)
    audio_preprocess_max_concurrent: int = Field(default=2, ge=1, le=10)
    # 기본 high-pass 컷오프 (요청에 명시 안 했을 때 사용; 0이면 비활성)
    audio_preprocess_default_high_pass_hz: int = Field(default=0, ge=0, le=500)

    # SPEC-STATS-001: 회의 통계 대시보드 설정
    # 키워드 빈도 상위 N개 반환
    statistics_keyword_top_n: int = Field(default=20, ge=1, le=200)
    # 키워드로 계산할 최소 글자 수 (한글 1글자, 영어 1글자 구분 없이 공통)
    statistics_keyword_min_length: int = Field(default=2, ge=1, le=10)

    # SPEC-KEYWORD-001: 자동 키워드 추천 설정
    keyword_max_keywords: int = Field(default=20, ge=1, le=100)
    keyword_min_score: float = Field(default=0.05, ge=0.0, le=1.0)
    keyword_min_term_length: int = Field(default=2, ge=1, le=20)
    keyword_tfidf_weight: float = Field(default=0.6, ge=0.0, le=1.0)
    keyword_textrank_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    keyword_textrank_window: int = Field(default=4, ge=2, le=10)
    keyword_cluster_similarity_threshold: float = Field(default=0.34, ge=0.0, le=1.0)
    keyword_history_limit: int = Field(default=20, ge=1, le=200)
    keyword_result_ttl: int = Field(default=604800, ge=60)
    keyword_max_text_chars: int = Field(default=100000, ge=1000, le=1000000)

    # SPEC-RELATED-001: 관련 회의 추천(Related Meetings) 설정
    # 요청 시 limit 미지정 기본값과 상한 (사용자 입력 검증에 사용)
    related_meetings_default_limit: int = Field(default=5, ge=1, le=50)
    related_meetings_max_limit: int = Field(default=20, ge=1, le=100)
    # 기준 회의에서 추출해 매칭에 사용할 상위 키워드 개수
    related_meetings_keyword_count: int = Field(default=10, ge=1, le=50)
    # 관련 회의로 인정하기 위한 최소 공유 키워드 수
    related_meetings_min_shared: int = Field(default=1, ge=0, le=20)

    # REQ-SEC-009/REQ-SEC-010: CORS 설정
    # 허용할 HTTP 메서드 목록 (와일드카드 금지)
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PATCH", "DELETE"]
    )
    # 허용할 Origins 목록 (기본: 로컬 개발 환경)
    cors_allow_origins: list[str] = Field(default_factory=lambda: list(_DEFAULT_CORS_ORIGINS))

    @field_validator("temp_dir", "results_dir", "templates_dir", mode="before")
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

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        normalized = v.strip().lower()
        if normalized not in _ALLOWED_ENVIRONMENTS:
            allowed = ", ".join(sorted(_ALLOWED_ENVIRONMENTS))
            raise ValueError(f"environment는 다음 중 하나여야 합니다: {allowed}")
        return normalized

    @field_validator("cors_allow_methods")
    @classmethod
    def validate_cors_allow_methods(cls, v: list[str]) -> list[str]:
        methods = [method.strip().upper() for method in v if method.strip()]
        if not methods:
            raise ValueError("cors_allow_methods는 최소 1개 이상의 메서드를 포함해야 합니다")
        if "*" in methods:
            raise ValueError("cors_allow_methods에 와일드카드(*)를 사용할 수 없습니다")
        return methods

    @field_validator("cors_allow_origins")
    @classmethod
    def validate_cors_allow_origins(cls, v: list[str]) -> list[str]:
        origins = [origin.strip() for origin in v if origin.strip()]
        if not origins:
            raise ValueError("cors_allow_origins는 최소 1개 이상의 origin을 포함해야 합니다")
        if "*" in origins:
            raise ValueError(
                "allow_credentials=True 환경에서는 cors_allow_origins에 '*'를 사용할 수 없습니다"
            )

        for origin in origins:
            parsed = urlparse(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError(f"유효하지 않은 origin 형식입니다: {origin}")
        return origins

    @model_validator(mode="after")
    def validate_production_security(self) -> "Settings":
        if self.environment == "production" and not self.api_keys:
            raise ValueError("production 환경에서는 API_KEYS를 반드시 설정해야 합니다")
        jwt_secret = self.jwt_secret.strip()
        if self.environment == "production" and (
            not jwt_secret or jwt_secret == "dev-insecure-change-me"
        ):
            raise ValueError("production 환경에서는 JWT_SECRET을 반드시 설정해야 합니다")
        if self.environment == "production" and len(jwt_secret) < 32:
            raise ValueError("production 환경에서는 JWT_SECRET은 최소 32자 이상이어야 합니다")
        if self.environment == "production" and not self.firebase_credentials_path:
            raise ValueError(
                "production 환경에서는 FIREBASE_CREDENTIALS_PATH를 반드시 설정해야 합니다"
            )
        if self.environment == "production" and not self.llm_api_key:
            raise ValueError("production 환경에서는 LLM API key를 반드시 설정해야 합니다")
        if self.environment == "production":
            for origin in self.cors_allow_origins:
                parsed = urlparse(origin)
                hostname = (parsed.hostname or "").lower()
                if hostname in {"localhost", "127.0.0.1", "::1"} or hostname.endswith(
                    ".localhost"
                ):
                    raise ValueError(
                        "production 환경에서는 localhost CORS origin을 사용할 수 없습니다"
                    )
                if parsed.scheme != "https":
                    raise ValueError("production 환경에서는 HTTPS CORS origin만 허용됩니다")
        return self

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

    @property
    def llm_api_key(self) -> str:
        return self.zai_api_key.strip()

    @property
    def llm_base_url(self) -> str:
        configured = self.zai_base_url.strip()
        if configured:
            return configured.rstrip("/")
        return _ZAI_CODING_PLAN_BASE_URL


settings = Settings()
