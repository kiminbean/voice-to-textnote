"""
REQ-ERR-003 ~ REQ-ERR-006: 전역 예외 핸들러 등록 모듈
모든 예외를 일관된 JSON 형식으로 변환하고, 프로덕션에서
스택 트레이스를 클라이언트에 노출하지 않는다.
"""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.app.exceptions import VoiceNoteError
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def _get_request_id() -> str:
    """
    structlog 컨텍스트에서 request_id를 추출한다.
    RequestIDMiddleware가 바인딩한 값을 가져오거나 "unknown" 반환.
    """
    return structlog.contextvars.get_contextvars().get("request_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    """
    FastAPI 앱에 전역 예외 핸들러를 등록한다.

    등록 핸들러:
    - VoiceNoteError: 도메인 예외 → HTTP 상태 코드 및 에러 코드 반환
    - RequestValidationError: 요청 유효성 검사 실패 → 422 + 필드별 상세 오류
    - Exception: 처리되지 않은 예외 → 500 + 내부 오류 메시지 숨김
    """
    app.add_exception_handler(VoiceNoteError, _voicenote_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_error_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


async def _voicenote_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    REQ-ERR-003, REQ-ERR-004: 도메인 예외 처리기
    VoiceNoteError 및 하위 예외를 일관된 JSON 형식으로 반환한다.
    """
    # FastAPI add_exception_handler는 Exception 타입을 요구하므로 다운캐스팅
    domain_exc = exc if isinstance(exc, VoiceNoteError) else None
    if domain_exc is None:
        return await _unhandled_exception_handler(request, exc)

    logger.warning(
        "도메인 예외 발생",
        error_code=domain_exc.error_code,
        message=domain_exc.message,
        status_code=domain_exc.status_code,
    )

    return JSONResponse(
        status_code=domain_exc.status_code,
        content={
            "error_code": domain_exc.error_code,
            "message": domain_exc.message,
            "request_id": _get_request_id(),
        },
    )


async def _validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    REQ-ERR-006: 요청 유효성 검사 실패 처리기
    FastAPI의 RequestValidationError를 필드별 상세 오류 정보와 함께 반환한다.
    """
    # FastAPI add_exception_handler는 Exception 타입을 요구하므로 다운캐스팅
    validation_exc = exc if isinstance(exc, RequestValidationError) else None
    if validation_exc is None:
        return await _unhandled_exception_handler(request, exc)

    # pydantic ValidationError의 각 오류 항목을 직렬화 가능한 형식으로 변환
    details = []
    for error in validation_exc.errors():
        details.append(
            {
                "field": " -> ".join(str(loc) for loc in error.get("loc", [])),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
        )

    logger.warning(
        "요청 유효성 검사 실패",
        detail_count=len(details),
    )

    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "요청 데이터 유효성 검사에 실패했습니다.",
            "request_id": _get_request_id(),
            "details": details,
        },
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    REQ-ERR-003, REQ-ERR-005: 처리되지 않은 예외 처리기
    예상치 못한 예외를 500 응답으로 변환하고,
    내부 오류 세부 정보를 클라이언트에 노출하지 않는다.
    """
    # 내부적으로는 전체 오류 정보를 로깅 (운영자가 디버깅할 수 있도록)
    logger.error(
        "처리되지 않은 예외 발생",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        exc_info=True,
    )

    # 클라이언트에는 일반적인 오류 메시지만 반환 (스택 트레이스 숨김)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "message": "서버 내부 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
            "request_id": _get_request_id(),
        },
    )
