"""
SPEC-MOBILE-001: DB-backed PushService 테스트

TASK-003: PushService를 인메모리에서 DB-backed로 리팩토링
TDD 접근법:
1. DB 연동 메서드 테스트 (register_device, unregister_device, get_user_tokens)
2. 기존 인메모리 메서드와 호환성 유지 확인
3. send_to_user 메서드 DB 통합 테스트
"""

import pytest
from sqlalchemy import select

from backend.db.device_token_models import DeviceToken
from backend.services.push_service import get_push_service


class TestPushServiceDBBacked:
    """REQ-MOBILE-001~006: DB-backed PushService 테스트"""

    @pytest.mark.asyncio
    async def test_register_device_creates_record(self, db_session):
        """DB에 디바이스 토큰 레코드 생성"""
        service = get_push_service()

        # 디바이스 등록
        await service.register_device(
            fcm_token="test_fcm_token_123",
            platform="ios",
            db=db_session,
            user_id="test-user-001",
        )

        # DB 조회
        result = await db_session.execute(
            select(DeviceToken).where(DeviceToken.fcm_token == "test_fcm_token_123")
        )
        device = result.scalar_one()

        assert device is not None
        assert device.user_id == "test-user-001"
        assert device.fcm_token == "test_fcm_token_123"
        assert device.platform == "ios"
        assert device.is_active is True

    @pytest.mark.asyncio
    async def test_register_device_updates_existing_token(self, db_session):
        """동일 fcm_token으로 재등록 시 업데이트 (upsert)"""
        service = get_push_service()

        # 첫 번째 등록
        await service.register_device(
            fcm_token="same_token",
            platform="ios",
            db=db_session,
            user_id="user-001",
        )

        # 두 번째 등록 (다른 user_id, platform)
        await service.register_device(
            fcm_token="same_token",
            platform="android",
            db=db_session,
            user_id="user-002",
        )

        # DB 조회 - 최신 정보로 업데이트됨
        result = await db_session.execute(
            select(DeviceToken).where(DeviceToken.fcm_token == "same_token")
        )
        device = result.scalar_one()

        assert device.user_id == "user-002"  # 업데이트됨
        assert device.platform == "android"

    @pytest.mark.asyncio
    async def test_unregister_device_deactivates_token(self, db_session):
        """디바이스 해제 시 is_active=False로 설정"""
        service = get_push_service()

        # 디바이스 등록
        await service.register_device(
            fcm_token="token_to_delete",
            platform="ios",
            db=db_session,
            user_id="user-001",
        )

        # 해제
        await service.unregister_device(db=db_session, fcm_token="token_to_delete")

        # DB 조회 - 비활성화됨
        result = await db_session.execute(
            select(DeviceToken).where(DeviceToken.fcm_token == "token_to_delete")
        )
        device = result.scalar_one()

        assert device.is_active is False

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_token_succeeds(self, db_session):
        """존재하지 않는 토큰 해제 시도 - 실패하지 않음 (멱등성)"""
        service = get_push_service()

        # 존재하지 않는 토큰 해제 - 예외 발생하지 않음
        await service.unregister_device(db=db_session, fcm_token="nonexistent_token")

        # 테스트 통과 = 예외 없이 성공

    @pytest.mark.asyncio
    async def test_get_user_tokens_returns_active_only(self, db_session):
        """사용자의 활성 토큰만 반환"""
        service = get_push_service()

        # 3개 디바이스 등록
        await service.register_device(
            fcm_token="token1", platform="ios", db=db_session, user_id="user-001"
        )
        await service.register_device(
            fcm_token="token2", platform="android", db=db_session, user_id="user-001"
        )
        await service.register_device(
            fcm_token="token3", platform="ios", db=db_session, user_id="user-001"
        )

        # token2 비활성화
        await service.unregister_device(db=db_session, fcm_token="token2")

        # 사용자 토큰 조회
        tokens = await service.get_user_tokens(db=db_session, user_id="user-001")

        # 활성 토큰만 반환
        assert len(tokens) == 2
        assert "token1" in tokens
        assert "token3" in tokens
        assert "token2" not in tokens

    @pytest.mark.asyncio
    async def test_get_user_tokens_empty_for_new_user(self, db_session):
        """신규 사용자는 빈 리스트 반환"""
        service = get_push_service()

        tokens = await service.get_user_tokens(db=db_session, user_id="new_user")

        assert tokens == []

    @pytest.mark.asyncio
    async def test_invalidate_token_sets_inactive(self, db_session):
        """토큰 무효화 메서드 (unregister_device와 동일)"""
        service = get_push_service()

        # 디바이스 등록
        await service.register_device(
            fcm_token="token_to_invalidate",
            platform="ios",
            db=db_session,
            user_id="user-001",
        )

        # 무효화
        await service.invalidate_token(db=db_session, fcm_token="token_to_invalidate")

        # DB 확인
        result = await db_session.execute(
            select(DeviceToken).where(DeviceToken.fcm_token == "token_to_invalidate")
        )
        device = result.scalar_one()

        assert device.is_active is False

    @pytest.mark.asyncio
    async def test_send_to_user_with_meeting_id(self, db_session):
        """REQ-MOBILE-006: 사용자에게 meeting_id 포함 푸시 전송"""
        service = get_push_service()

        # 사용자 디바이스 등록
        await service.register_device(
            fcm_token="token1", platform="ios", db=db_session, user_id="user-001"
        )
        await service.register_device(
            fcm_token="token2", platform="android", db=db_session, user_id="user-001"
        )

        # 푸시 전송
        result = await service.send_to_user(
            db=db_session,
            user_id="user-001",
            meeting_id="meeting-123",
            title="회의록 완료",
            body="회의록이 생성되었습니다.",
        )

        # MVP: mock 전송으로 항상 성공
        assert result["success_count"] == 2
        assert result["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_send_to_user_no_devices(self, db_session):
        """등록된 디바이스가 없는 사용자에게 전송"""
        service = get_push_service()

        # 디바이스 없는 사용자에게 전송
        result = await service.send_to_user(
            db=db_session,
            user_id="user-without-devices",
            meeting_id="meeting-123",
            title="테스트",
            body="테스트",
        )

        # 성공 0, 실패 0
        assert result["success_count"] == 0
        assert result["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_backward_compatibility_in_memory_fallback(self, db_session):
        """DB가 None인 경우 인메모리 모드로 폴백 (기존 테스트 호환성)"""
        service = get_push_service()

        # DB 없이 등록 (인메모리 모드)
        await service.register_device(device_id="device-001", fcm_token="memory_token")

        # 인메모리 저장소에서 조회
        devices = service.get_all_devices()
        assert "device-001" in devices
        assert devices["device-001"] == "memory_token"

    @pytest.mark.asyncio
    async def test_backward_compatibility_unregister_in_memory(self):
        """인메모리 모드에서 디바이스 해제"""
        service = get_push_service()

        # 인메모리 등록
        await service.register_device(device_id="device-001", fcm_token="memory_token")

        # 인메모리 해제
        deleted = await service.unregister_device(device_id="device-001")

        assert deleted is True
        assert "device-001" not in service.get_all_devices()

    @pytest.mark.asyncio
    async def test_send_to_user_with_custom_data(self, db_session):
        """사용자 푸시에 커스텀 데이터 포함"""
        service = get_push_service()

        await service.register_device(
            fcm_token="token1", platform="ios", db=db_session, user_id="user-001"
        )

        # 커스텀 데이터 포함 전송
        result = await service.send_to_user(
            db=db_session,
            user_id="user-001",
            meeting_id="meeting-123",
            title="새 메시지",
            body="내용",
            data={"action": "open_meeting", "screen": "detail"},
        )

        assert result["success_count"] == 1
