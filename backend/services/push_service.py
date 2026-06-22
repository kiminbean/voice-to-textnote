"""
SPEC-MOBILE-001: Firebase Cloud Messaging (FCM) Push Service

REQ-MOBILE-004: 단일 디바이스 푸시 알림 전송
REQ-MOBILE-005: 멀티캐스트 푸시 알림 전송
REQ-MOBILE-006: FCM 토큰 무효화 처리

TASK-003: DB-backed 디바이스 관리 (DeviceToken 모델 사용)
MVP: 인메모리 저장 (dict) 사용, Firebase 프로젝트 생성 필요 없음
"""

import asyncio
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# firebase-admin 미설치 시에도 동작하도록 조건부 임포트
try:
    from firebase_admin.exceptions import FirebaseError, InvalidArgumentError
except ImportError:
    FirebaseError = Exception  # type: ignore[misc,assignment]
    InvalidArgumentError = ValueError  # type: ignore[misc,assignment]

from backend.app.config import settings
from backend.utils.logger import get_logger

# 로거 설정
logger = get_logger(__name__)


def _fcm_token_log_label(token: str | None) -> str:
    """FCM 토큰 원문이나 접두사를 로그에 남기지 않는 진단용 라벨."""
    return f"fcm_token_present={token is not None}, fcm_token_length={len(token or '')}"


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
        """Push Service 초기화"""
        self._devices: dict[str, str] = {}
        self._firebase_initialized = False
        self._is_mock_mode = True

    def _ensure_firebase_initialized(self) -> None:
        """Firebase Admin SDK 초기화 (credentials 있으면 실제, 없으면 MOCK)"""
        if self._firebase_initialized:
            return

        creds_path = settings.firebase_credentials_path
        if not creds_path:
            if settings.environment == "production":
                raise RuntimeError("Firebase credentials are required in production")
            logger.info("Firebase Admin SDK 초기화 (MOCK 모드)")
            self._is_mock_mode = True
            self._firebase_initialized = True
            return

        try:
            import firebase_admin
            from firebase_admin import credentials

            if not firebase_admin._apps:
                cred = credentials.Certificate(creds_path)
                firebase_admin.initialize_app(cred)
                logger.info("Firebase Admin SDK 초기화 완료 (프로덕션 모드)")
            else:
                logger.info("Firebase Admin SDK 이미 초기화됨")
            self._is_mock_mode = False
            self._firebase_initialized = True
        except Exception as e:
            if settings.environment == "production":
                raise RuntimeError("Firebase initialization failed in production") from e
            logger.warning(f"Firebase 초기화 실패, MOCK 모드로 폴백: {e}")
            self._is_mock_mode = True
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
            if self._is_mock_mode:
                logger.info(
                    f"[MOCK] FCM 전송: title={title}, body={body}, {_fcm_token_log_label(token)}"
                )
                if data:
                    logger.info(f"[MOCK] FCM 데이터: {data}")
            else:
                from firebase_admin import messaging

                message = messaging.Message(
                    notification=messaging.Notification(title=title, body=body),
                    data=data or {},
                    token=token,
                )
                await asyncio.to_thread(messaging.send, message)

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

        if self._is_mock_mode:
            logger.info(f"[MOCK] FCM 멀티캐스트: {len(tokens)}개 디바이스")
            logger.info(f"[MOCK] title={title}, body={body}")
            return {
                "success_count": len(tokens),
                "failure_count": 0,
                "invalid_tokens": [],
            }

        from firebase_admin import messaging

        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            tokens=tokens,
        )
        response = await asyncio.to_thread(messaging.send_each_for_multicast, message)
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count,
            "invalid_tokens": [],
        }

    async def register_device(
        self,
        device_id: str | None = None,
        fcm_token: str | None = None,
        *,
        db: AsyncSession | None = None,
        user_id: str | None = None,
        platform: str | None = None,
    ) -> None:
        """
        TASK-003: 디바이스 등록 (DB-backed 또는 인메모리)

        새로운 DB-backed 방식 (권장):
            await register_device(fcm_token=..., platform=..., db=..., user_id=..., device_id=...)

        레거시 인메모리 방식 (하위 호환성):
            register_device(device_id, fcm_token) - 동기식, 반환값 없음

        Args:
            device_id: 디바이스 고유 식별자 (DB 모드에서는 선택, 인메모리 모드에서는 필수)
            fcm_token: FCM 등록 토큰
            db: AsyncSession (DB 모드, keyword-only)
            user_id: 사용자 ID (DB 모드, keyword-only)
            platform: 디바이스 플랫폼 (DB 모드, keyword-only)
        """
        # DB 모드 (keyword-only 파라미터로 구분)
        if (
            db is not None
            and user_id is not None
            and platform is not None
            and fcm_token is not None
        ):
            from backend.db.device_token_models import DeviceToken

            existing = None
            if device_id:
                result = await db.execute(
                    select(DeviceToken)
                    .where(DeviceToken.user_id == user_id)
                    .where(DeviceToken.device_id == device_id)
                )
                existing = result.scalar_one_or_none()

            token_result = await db.execute(
                select(DeviceToken).where(DeviceToken.fcm_token == fcm_token)
            )
            existing_by_token = token_result.scalar_one_or_none()
            if existing is None:
                existing = existing_by_token
            elif existing_by_token is not None and existing_by_token.id != existing.id:
                existing.is_active = False
                existing = existing_by_token

            if existing:
                # 업데이트
                existing.user_id = user_id
                existing.platform = platform
                existing.device_id = device_id
                existing.fcm_token = fcm_token
                existing.is_active = True
                logger.info(
                    f"디바이스 토큰 업데이트: user_id={user_id}, "
                    f"device_id={device_id}, {_fcm_token_log_label(fcm_token)}"
                )
            else:
                # 신규 생성
                new_device = DeviceToken(
                    user_id=user_id,
                    fcm_token=fcm_token,
                    device_id=device_id,
                    platform=platform,
                    is_active=True,
                )
                db.add(new_device)
                logger.info(f"디바이스 등록: user_id={user_id}, platform={platform}")

            await db.commit()
            return

        # 인메모리 모드 (레거시 - 위치 인자로 호출 가능)
        if device_id is not None and fcm_token is not None:
            self._devices[device_id] = fcm_token
            logger.info(f"디바이스 등록 (인메모리): device_id={device_id}")
            return

        raise ValueError("잘못된 파라미터 조합")

    async def unregister_device(
        self,
        device_id: str | None = None,
        *,
        db: AsyncSession | None = None,
        fcm_token: str | None = None,
        user_id: str | None = None,
    ) -> None | bool:
        """
        TASK-003: 디바이스 해제 (DB-backed 또는 인메모리)

        새로운 DB-backed 방식 (권장):
            await unregister_device(db=..., fcm_token=...)
            await unregister_device(db=..., user_id=..., device_id=...)

        레거시 인메모리 방식 (하위 호환성):
            unregister_device(device_id) - 동기식, bool 반환

        Args:
            device_id: 디바이스 고유 식별자 (DB 모드에서는 user_id와 함께 사용, 인메모리 모드)
            db: AsyncSession (DB 모드, keyword-only)
            fcm_token: FCM 등록 토큰 (DB 모드, keyword-only)
            user_id: 사용자 ID (DB device_id 모드)

        Returns:
            None (DB 모드)
            bool (인메모리 모드 - 하위 호환성)
        """
        # DB 모드 (keyword-only 파라미터로 구분)
        if db is not None and (fcm_token is not None or (user_id is not None and device_id is not None)):
            from backend.db.device_token_models import DeviceToken

            query = select(DeviceToken)
            if fcm_token is not None:
                query = query.where(DeviceToken.fcm_token == fcm_token)
            else:
                query = (
                    query.where(DeviceToken.user_id == user_id)
                    .where(DeviceToken.device_id == device_id)
                    .where(DeviceToken.is_active)
                )
            result = await db.execute(query)
            device = result.scalar_one_or_none()

            if device:
                device.is_active = False
                await db.commit()
                logger.info(
                    f"디바이스 비활성화: user_id={device.user_id}, "
                    f"device_id={device.device_id}, {_fcm_token_log_label(device.fcm_token)}"
                )
            # 존재하지 않아도 멱등성으로 성공 (예외 없음)
            return None

        # 인메모리 모드 (레거시 - 위치 인자로 호출 가능)
        if device_id is not None:
            if device_id in self._devices:
                del self._devices[device_id]
                logger.info(f"디바이스 해제 (인메모리): device_id={device_id}")
                return True
            return False

        raise ValueError("잘못된 파라미터 조합")

    async def get_user_tokens(self, db: AsyncSession, user_id: str) -> list[str]:
        """
        TASK-003: 사용자의 활성 FCM 토큰 목록 조회

        Args:
            db: AsyncSession
            user_id: 사용자 ID

        Returns:
            활성화된 FCM 토큰 리스트
        """
        from backend.db.device_token_models import DeviceToken

        result = await db.execute(
            select(DeviceToken.fcm_token)
            .where(DeviceToken.user_id == user_id)
            .where(DeviceToken.is_active)
        )
        tokens = [row[0] for row in result.all()]
        return tokens

    async def invalidate_token(self, db: AsyncSession, fcm_token: str) -> None:
        """
        TASK-003: 토큰 무효화 (unregister_device와 동일)

        Args:
            db: AsyncSession
            fcm_token: 무효화할 FCM 토큰
        """
        await self.unregister_device(db=db, fcm_token=fcm_token)

    async def send_to_user(
        self,
        db: AsyncSession,
        user_id: str,
        meeting_id: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        TASK-003: 사용자에게 푸시 전송 (DB에서 토큰 조회)

        Args:
            db: AsyncSession
            user_id: 사용자 ID
            meeting_id: 회의 ID (페이로드에 포함)
            title: 알림 제목
            body: 알림 본문
            data: 추가 데이터

        Returns:
            {"success_count": int, "failure_count": int, "invalid_tokens": list}
        """
        # 사용자 토큰 조회
        tokens = await self.get_user_tokens(db, user_id)

        if not tokens:
            logger.warning(f"사용자에게 활성 토큰 없음: user_id={user_id}")
            return {"success_count": 0, "failure_count": 0, "invalid_tokens": []}

        # meeting_id를 데이터에 포함
        payload = data or {}
        payload["meeting_id"] = meeting_id

        # 멀티캐스트 전송
        return await self.send_multicast(tokens=tokens, title=title, body=body, data=payload)

    def get_all_devices(self) -> dict[str, str]:
        """
        등록된 모든 디바이스 반환 (레거시 인메모리, 하위 호환성용)

        Returns:
            {device_id: fcm_token} 딕셔너리
        """
        return self._devices.copy()

    # ========================================================================
    # 동기식 래퍼 메서드 (기존 테스트 호환성용 - 비권장)
    # ========================================================================

    def register_device_sync(self, device_id: str, fcm_token: str) -> None:
        """
        레거시 인메모리 디바이스 등록 (동기식, 기존 테스트 호환성)

        Args:
            device_id: 디바이스 고유 식별자
            fcm_token: FCM 등록 토큰
        """
        self._devices[device_id] = fcm_token
        logger.info(f"디바이스 등록 (인메모리 동기): device_id={device_id}")

    def unregister_device_sync(self, device_id: str) -> bool:
        """
        레거시 인메모리 디바이스 해제 (동기식, 기존 테스트 호환성)

        Args:
            device_id: 디바이스 고유 식별자

        Returns:
            삭제 성공 여부
        """
        if device_id in self._devices:
            del self._devices[device_id]
            logger.info(f"디바이스 해제 (인메모리 동기): device_id={device_id}")
            return True
        return False


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
