"""
REQ-ERR-001, REQ-ERR-002: 도메인 예외 계층 구조
VoiceNoteError를 기반으로 한 도메인별 예외 클래스 정의
"""


class VoiceNoteError(Exception):
    """
    VoiceNote 애플리케이션의 기본 예외 클래스

    모든 도메인 예외는 이 클래스를 상속한다.
    - error_code: 클라이언트가 처리할 수 있는 기계 판독 가능 오류 코드
    - message: 사람이 읽을 수 있는 오류 메시지
    - status_code: HTTP 응답 상태 코드
    """

    def __init__(
        self,
        *,
        error_code: str,
        message: str,
        status_code: int,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


class AudioProcessingError(VoiceNoteError):
    """
    오디오 처리 관련 예외

    파일 형식 오류, 코덱 문제, 오디오 변환 실패 등 오디오 처리 중
    발생하는 오류를 나타낸다.
    기본 상태 코드: 422 (Unprocessable Entity)
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = "AUDIO_PROCESSING_ERROR",
        status_code: int = 422,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class StorageError(VoiceNoteError):
    """
    저장소 관련 예외

    파일 저장, 조회, 삭제 등 저장소 작업 중 발생하는 오류를 나타낸다.
    기본 상태 코드: 500 (Internal Server Error)
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = "STORAGE_ERROR",
        status_code: int = 500,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class PipelineError(VoiceNoteError):
    """
    파이프라인 처리 관련 예외

    STT, 화자 분리, 요약 등 처리 파이프라인 실행 중 발생하는
    오류를 나타낸다.
    기본 상태 코드: 500 (Internal Server Error)
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = "PIPELINE_ERROR",
        status_code: int = 500,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class NotFoundError(VoiceNoteError):
    """
    리소스를 찾을 수 없음 (404)

    요청한 리소스가 존재하지 않을 때 발생하는 예외
    기본 상태 코드: 404 (Not Found)
    """

    def __init__(
        self,
        *,
        message: str = "리소스를 찾을 수 없습니다",
        error_code: str = "NOT_FOUND",
        status_code: int = 404,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class UnauthorizedError(VoiceNoteError):
    """
    인증 필요 (401)

    인증 정보가 없거나 유효하지 않을 때 발생하는 예외
    기본 상태 코드: 401 (Unauthorized)
    """

    def __init__(
        self,
        *,
        message: str = "인증이 필요합니다",
        error_code: str = "UNAUTHORIZED",
        status_code: int = 401,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class ForbiddenError(VoiceNoteError):
    """
    접근 권한 없음 (403)

    인증되었지만 요청한 리소스에 접근할 권한이 없을 때 발생하는 예외
    기본 상태 코드: 403 (Forbidden)
    """

    def __init__(
        self,
        *,
        message: str = "접근 권한이 없습니다",
        error_code: str = "FORBIDDEN",
        status_code: int = 403,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class ConflictError(VoiceNoteError):
    """
    리소스 충돌 (409)

    요청이 현재 서버 상태와 충돌할 때 발생하는 예외
    기본 상태 코드: 409 (Conflict)
    """

    def __init__(
        self,
        *,
        message: str,
        error_code: str = "CONFLICT",
        status_code: int = 409,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )


class RateLimitError(VoiceNoteError):
    """
    요청 제한 초과 (429)

    요청 속도 제한을 초과했을 때 발생하는 예외
    기본 상태 코드: 429 (Too Many Requests)
    """

    def __init__(
        self,
        *,
        message: str = "요청 제한을 초과했습니다",
        error_code: str = "RATE_LIMIT",
        status_code: int = 429,
    ) -> None:
        super().__init__(
            error_code=error_code,
            message=message,
            status_code=status_code,
        )
