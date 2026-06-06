"""
SPEC-MOBILE-001: Firebase Cloud Messaging (FCM) Push Service

REQ-MOBILE-004: 단일 디바이스 푸시 알림 전송
REQ-MOBILE-005: 멀티캐스트 푸시 알림 전송
REQ-MOBILE-006: FCM 토큰 무효화 처리

MVP: 인메모리 저장 (dict) 사용, Firebase 프로젝트 생성 필요 없음
"""

from typing import Any

# firebase-admin 미설치 시에도 동작하도록 조건부 임포트
try:
    from firebase_admin.exceptions import FirebaseError, InvalidArgumentError
except ImportError:
    FirebaseError = Exception  # type: ignore[misc,assignment]
    InvalidArgumentError = ValueError  # type: ignore[misc,assignment]

from backend.utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)


class PushService:
    """
    Firebase Cloud Messaging Push Service

    MVP 구현:
    - 인메모리 디바이스 저장 (dict)
    - Firebase Admin SDK mock (실제 전송 X)
    - 토큰 무효화 시뮬레이션

    프로덕션 이동 시:
    - 데이터베이스 연동
    - 실제 Firebase 프로젝트 설정
    - firebase_admin.credentials 패치 제거
    """

    def __init__(self) -> None:
        """Push Service 초기화 (인메모리 저장소)"""
        # MVP: 인메모리 디바이스 저장 {device_id: fcm_token}
        self._devices: dict[str, str] = {}
        # Firebase 초기화 상태 (MVP: 항상 False)
        self._firebase_initialized = False

    def _ensure_firebase_initialized(self) -> None:
        """
        Firebase Admin SDK 초기화 확인

        MVP: mock 사용으로 초기화 불필요
        프로덕션: FIREBASE_CREDENTIALS_PATH 환경변수로 초기화
        """
        if not self._firebase_initialized:
            logger.info("Firebase Admin SDK 초기화 (MVP: mock 모드)")
            # MVP: 실제 초기화 없이 mock 상태로 유지
            # 프로덕션: credentials.Certificate(...)로 초기화
            self._firebase_initialized = True

    async def send_push(
        self,
        token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """
        REQ-MOBILE-004: 단일 디바이스 푸시 알림 전송

        Args:
            token: FCM 등록 토큰
            title: 알림 제목
            body: 알림 본문
            data: (선택) 추가 데이터 payload

        Returns:
            전송 성공 여부

        Raises:
            InvalidArgumentError: 토큰 형식 오류
            FirebaseError: FCM API 오류
        """
        self._ensure_firebase_initialized()

        try:
            # MVP: 로그만 출력하고 성공 반환
            logger.info(
                f"[MOCK] FCM 전송: title={title}, body={body}, token={token[:20]}..."
            )
            if data:
                logger.info(f"[MOCK] FCM 데이터: {data}")

            # 프로덕션 코드 (현재 비활성화):
            # message = messaging.Message(
            #     notification=messaging.Notification(title=title, body=body),
            #     data=data or {},
            #     token=token,
            # )
            # messaging.send(message)

            return True

        except InvalidArgumentError as e:
            logger.error(f"FCM 토큰 무효: {e}")  # pragma: no cover
            raise  # pragma: no cover
        except FirebaseError as e:
            logger.error(f"FCM 전송 실패: {e}")
            return False

    async def send_multicast(
        self,
        tokens: list[str],
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        REQ-MOBILE-005: 멀티캐스트 푸시 알림 전송

        Args:
            tokens: FCM 등록 토큰 리스트
            title: 알림 제목
            body: 알림 본문
            data: (선택) 추가 데이터 payload

        Returns:
            {
                "success_count": 성공 수,
                "failure_count": 실패 수,
                "invalid_tokens": 무효 토큰 리스트
            }
        """
        self._ensure_firebase_initialized()

        if not tokens:
            logger.warning("FCM 멀티캐스트: 빈 토큰 리스트")
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        # MVP: 모든 토큰이 성공한 것으로 시뮬레이션
        logger.info(f"[MOCK] FCM 멀티캐스트: {len(tokens)}개 디바이스")
        logger.info(f"[MOCK] title={title}, body={body}")

        # 프로덕션 코드 (현재 비활성화):
        # message = messaging.MulticastMessage(
        #     notification=messaging.Notification(title=title, body=body),
        #     data=data or {},
        #     tokens=tokens,
        # )
        # response = messaging.send_multicast(message)
        # return {
        #     "success_count": response.success_count,
        #     "failure_count": response.failure_count,
        #     "invalid_tokens": [],  # response에서 추출 필요
        # }

        return {
            "success_count": len(tokens),
            "failure_count": 0,
            "invalid_tokens": [],
        }

    def register_device(self, device_id: str, fcm_token: str) -> None:
        """
        디바이스 등록 (MVP: 인메모리 저장)

        Args:
            device_id: 디바이스 고유 식별자
            fcm_token: FCM 등록 토큰
        """
        self._devices[device_id] = fcm_token
        logger.info(f"디바이스 등록: device_id={device_id}")

    def unregister_device(self, device_id: str) -> bool:
        """
        디바이스 등록 해제

        Args:
            device_id: 디바이스 고유 식별자

        Returns:
            삭제 성공 여부
        """
        if device_id in self._devices:
            del self._devices[device_id]
            logger.info(f"디바이스 해제: device_id={device_id}")
            return True
        return False

    def get_all_devices(self) -> dict[str, str]:
        """
        등록된 모든 디바이스 반환

        Returns:
            {device_id: fcm_token} 딕셔너리
        """
        return self._devices.copy()


# 싱글톤 인스턴스
_push_service: PushService | None = None


def get_push_service() -> PushService:
    """
    PushService 싱글톤 인스턴스 반환

    Returns:
        PushService 인스턴스
    """
    global _push_service
    if _push_service is None:
        _push_service = PushService()
    return _push_service
