"""SPEC-REFACTOR-001: 공통 에러 헬퍼 함수"""

from __future__ import annotations

from typing import NoReturn

from backend.app.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
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
