"""SPEC-REFACTOR-001: 공통 에러 헬퍼 함수"""

from __future__ import annotations

from typing import Any, NoReturn

from backend.app.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
    RequestEntityTooLargeError,
    ServiceUnavailableError,
    UnauthorizedError,
    UnprocessableEntityError,
)


def not_found(msg: str = "리소스를 찾을 수 없습니다", **kwargs: str) -> NoReturn:
    """
    NotFoundError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        NotFoundError: 404 에러
    """
    raise NotFoundError(
        message=msg,
        error_code=kwargs.get("error_code", "NOT_FOUND"),
        status_code=404,
    )


def unauthorized(msg: str = "인증이 필요합니다", **kwargs: str) -> NoReturn:
    """
    UnauthorizedError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        UnauthorizedError: 401 에러
    """
    raise UnauthorizedError(
        message=msg,
        error_code=kwargs.get("error_code", "UNAUTHORIZED"),
        status_code=401,
    )


def forbidden(msg: str = "접근 권한이 없습니다", **kwargs: str) -> NoReturn:
    """
    ForbiddenError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        ForbiddenError: 403 에러
    """
    raise ForbiddenError(
        message=msg,
        error_code=kwargs.get("error_code", "FORBIDDEN"),
        status_code=403,
    )


def conflict(msg: str, **kwargs: str) -> NoReturn:
    """
    ConflictError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        ConflictError: 409 에러
    """
    raise ConflictError(
        message=msg,
        error_code=kwargs.get("error_code", "CONFLICT"),
        status_code=409,
    )


def rate_limit(msg: str = "요청 제한을 초과했습니다", **kwargs: str) -> NoReturn:
    """
    RateLimitError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        RateLimitError: 429 에러
    """
    raise RateLimitError(
        message=msg,
        error_code=kwargs.get("error_code", "RATE_LIMIT"),
        status_code=429,
    )


def unprocessable(msg: str | list[dict[str, Any]] = "요청을 처리할 수 없습니다", **kwargs: str) -> NoReturn:
    """
    UnprocessableEntityError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        UnprocessableEntityError: 422 에러
    """
    raise UnprocessableEntityError(
        message=msg,
        error_code=kwargs.get("error_code", "UNPROCESSABLE_ENTITY"),
        status_code=422,
    )


def bad_request(msg: str = "잘못된 요청입니다", **kwargs: str) -> NoReturn:
    """
    BadRequestError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        BadRequestError: 400 에러
    """
    raise BadRequestError(
        message=msg,
        error_code=kwargs.get("error_code", "BAD_REQUEST"),
        status_code=400,
    )


def internal_error(msg: str = "서버 내부 오류가 발생했습니다", **kwargs: str) -> NoReturn:
    """
    InternalServerError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        InternalServerError: 500 에러
    """
    raise InternalServerError(
        message=msg,
        error_code=kwargs.get("error_code", "INTERNAL_SERVER_ERROR"),
        status_code=500,
    )


def request_entity_too_large(
    msg: str = "요청 크기가 허용 한도를 초과했습니다", **kwargs: str
) -> NoReturn:
    """
    RequestEntityTooLargeError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        RequestEntityTooLargeError: 413 에러
    """
    raise RequestEntityTooLargeError(
        message=msg,
        error_code=kwargs.get("error_code", "REQUEST_ENTITY_TOO_LARGE"),
        status_code=413,
    )


def service_unavailable(
    msg: str = "서비스를 일시적으로 사용할 수 없습니다", **kwargs: str
) -> NoReturn:
    """
    ServiceUnavailableError를 발생시키는 헬퍼 함수

    Args:
        msg: 에러 메시지
        **kwargs: error_code 등 추가 파라미터

    Raises:
        ServiceUnavailableError: 503 에러
    """
    raise ServiceUnavailableError(
        message=msg,
        error_code=kwargs.get("error_code", "SERVICE_UNAVAILABLE"),
        status_code=503,
    )


# --- Aliases (에이전트 마이그레이션 호환성) ---
too_many_requests = rate_limit
internal_server_error = internal_error
