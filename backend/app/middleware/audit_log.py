"""
감사 로깅 미들웨어
SPEC-LOG-001: API 요청에 대한 감사 로그 생성

REQ-LOG-001: 모든 API 요청에 감사 로그 생성
REQ-LOG-002: timestamp, request_id, method, path, status_code, client_ip, user_agent, duration_ms 포함
REQ-LOG-003: 민감 정보(x-api-key, authorization, cookie) 감사 로그에 미포함
REQ-LOG-004: /api/v1/health* 및 /metrics 경로 감사 로깅 스킵
REQ-LOG-005: 5초 초과 요청 WARNING 레벨로 로깅 (slow_request 마커 포함)
REQ-LOG-006: 엔드포인트별 접근 횟수 Prometheus Counter 추적
"""

import time
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter
from prometheus_client import registry as prom_registry
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import get_contextvars

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# 상수 정의
# ---------------------------------------------------------------------------

# REQ-LOG-003: 감사 로그에서 제외할 민감 헤더 목록 (소문자 정규화)
SENSITIVE_HEADERS: frozenset[str] = frozenset({"x-api-key", "authorization", "cookie"})

# REQ-LOG-004: 감사 로깅을 스킵할 경로 목록 (전방 일치 지원)
# /api/v1/health로 시작하는 모든 경로와 /metrics 경로 스킵
SKIP_PATHS: frozenset[str] = frozenset({"/api/v1/health", "/metrics"})

# REQ-LOG-005: 느린 요청 판단 임계값 (초)
SLOW_REQUEST_THRESHOLD_SECONDS: float = 5.0


# ---------------------------------------------------------------------------
# REQ-LOG-006: Prometheus 접근 카운터 (중복 등록 방지)
# ---------------------------------------------------------------------------


def _get_or_create_counter(name: str, documentation: str, labelnames: list[str]) -> Counter:
    """
    이미 등록된 Counter를 반환하거나 새로 생성

    테스트 환경에서 여러 앱 인스턴스가 생성될 때
    Prometheus 레지스트리에 동일 이름의 카운터가 중복 등록되는 것을 방지
    """
    existing = prom_registry.REGISTRY._names_to_collectors.get(name)
    if existing is not None:
        return existing  # type: ignore[return-value]
    return Counter(name, documentation, labelnames)


# 엔드포인트별 접근 횟수 카운터 (method, path 레이블로 세분화)
# @MX:ANCHOR: 전역 Prometheus Counter - 재생성 시 레지스트리 충돌 발생
# @MX:REASON: _get_or_create_counter로 중복 등록 방지, 테스트 격리 보장
API_ACCESS_COUNTER: Counter = _get_or_create_counter(
    "voicenote_api_access_total",
    "API 엔드포인트별 접근 횟수",
    ["method", "path"],
)


# ---------------------------------------------------------------------------
# REQ-LOG-001~006: 감사 로깅 미들웨어
# ---------------------------------------------------------------------------


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    모든 API 요청에 대한 감사 로그를 생성하는 미들웨어

    REQ-LOG-001: 모든 API 요청 감사 로그 생성
    REQ-LOG-002: 필수 필드 포함 (timestamp, request_id, method, path 등)
    REQ-LOG-003: 민감 정보 제외 (x-api-key, authorization, cookie)
    REQ-LOG-004: 헬스체크·메트릭스 경로 스킵
    REQ-LOG-005: 5초 초과 요청 WARNING 레벨 로깅 (slow_request=True 마커)
    REQ-LOG-006: Prometheus 카운터 증가 (method, path 레이블)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """요청 처리 및 감사 로그 기록"""
        path = request.url.path

        # REQ-LOG-004: 스킵 경로면 로깅 없이 통과
        if self._should_skip(path):
            return await call_next(request)

        # REQ-LOG-002: 처리 시간 측정 시작 (perf_counter - 고해상도 단조 시계)
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_seconds = time.perf_counter() - start_time

        # REQ-LOG-006: Prometheus 접근 카운터 증가
        API_ACCESS_COUNTER.labels(method=request.method, path=path).inc()

        # REQ-LOG-002: 감사 로그 필드 구성
        audit_fields = self._build_audit_fields(request, response, duration_seconds)

        # REQ-LOG-005: 처리 시간 기준으로 로그 레벨 결정
        if duration_seconds > SLOW_REQUEST_THRESHOLD_SECONDS:
            logger.warning("audit", slow_request=True, **audit_fields)
        else:
            logger.info("audit", **audit_fields)

        return response

    def _should_skip(self, path: str) -> bool:
        """
        감사 로깅 스킵 여부 판단

        REQ-LOG-004: SKIP_PATHS 목록과 전방 일치로 확인
        예: /api/v1/health, /api/v1/health/ready, /api/v1/health/live 모두 스킵
        """
        for skip_path in SKIP_PATHS:
            if path == skip_path or path.startswith(skip_path + "/"):
                return True
        return False

    def _build_audit_fields(
        self,
        request: Request,
        response: Response,
        duration_seconds: float,
    ) -> dict[str, Any]:
        """
        감사 로그 필드 딕셔너리 구성

        REQ-LOG-002: 필수 필드만 포함
        REQ-LOG-003: SENSITIVE_HEADERS에 속한 헤더는 절대 포함하지 않음
        structlog contextvars에서 request_id를 읽어 포함
        """
        # REQ-LOG-002: structlog context에서 request_id 추출
        # RequestIDMiddleware가 먼저 실행됐다면 자동으로 바인딩돼 있음
        ctx = get_contextvars()
        request_id = ctx.get("request_id", "")

        return {
            "timestamp": datetime.now(tz=UTC).isoformat(),
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "client_ip": self._get_client_ip(request),
            "user_agent": request.headers.get("user-agent", ""),
            "duration_ms": round(duration_seconds * 1000.0, 3),
        }

    def _get_client_ip(self, request: Request) -> str:
        """
        클라이언트 실제 IP 추출

        프록시·로드밸런서 환경에서 X-Forwarded-For 헤더 우선 사용
        직접 연결 시 request.client.host 사용
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # X-Forwarded-For: client, proxy1, proxy2 → 첫 번째 IP가 실제 클라이언트
            return forwarded_for.split(",")[0].strip()

        if request.client:
            return request.client.host

        return ""
