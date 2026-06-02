"""
SPEC-MOBILE-001: FCM 디바이스 등록 API 테스트

TDD 접근법:
1. Device 스키마 유효성 검사 테스트
2. Push Service 기능 테스트
3. Device API 엔드포인트 테스트
"""

import pytest
from fastapi import status
from pydantic import ValidationError

from backend.schemas.device import (
    DeviceListResponse,
    DeviceRegisterRequest,
    DeviceResponse,
)

# ---------------------------------------------------------------------------
# Device 스키마 테스트
# ---------------------------------------------------------------------------


class TestDeviceRegisterRequest:
    """REQ-MOBILE-001: DeviceRegisterRequest 스키마 검증"""

    def test_valid_request(self):
        """유효한 디바이스 등록 요청"""
        req = DeviceRegisterRequest(
            fcm_token="test_fcm_token_12345",
            platform="ios",
            device_id="test_device_001",
        )
        assert req.fcm_token == "test_fcm_token_12345"
        assert req.platform == "ios"
        assert req.device_id == "test_device_001"

    def test_valid_request_without_device_id(self):
        """device_id 없는 유효한 요청"""
        req = DeviceRegisterRequest(
            fcm_token="test_fcm_token_12345",
            platform="android",
        )
        assert req.fcm_token == "test_fcm_token_12345"
        assert req.platform == "android"
        assert req.device_id is None

    def test_invalid_empty_fcm_token(self):
        """빈 FCM 토큰은 거부됨"""
        with pytest.raises(ValidationError) as exc:
            DeviceRegisterRequest(
                fcm_token="",  # 빈 문자열
                platform="ios",
            )
        errors = exc.value.errors()
        assert any(e["loc"] == ("fcm_token",) and e["type"] == "string_too_short" for e in errors)

    def test_invalid_platform(self):
        """잘못된 플랫폼은 거부됨"""
        with pytest.raises(ValidationError) as exc:
            DeviceRegisterRequest(
                fcm_token="test_token",
                platform="windows",  # 잘못된 플랫폼
            )
        errors = exc.value.errors()
        assert any(e["loc"] == ("platform",) for e in errors)


class TestDeviceResponse:
    """REQ-MOBILE-002: DeviceResponse 스키마"""

    def test_valid_response(self):
        """유효한 디바이스 응답"""
        from datetime import datetime
        from uuid import uuid4

        device_id = uuid4()
        now = datetime.now()

        response = DeviceResponse(
            id=device_id,
            fcm_token="test_token",
            platform="ios",
            device_id="device_001",
            created_at=now,
            updated_at=now,
        )
        assert response.id == device_id
        assert response.fcm_token == "test_token"
        assert response.platform == "ios"

    def test_response_serialization(self):
        """DeviceResponse JSON 직렬화"""
        from datetime import UTC, datetime
        from uuid import uuid4

        device_id = uuid4()
        now = datetime.now(UTC)

        response = DeviceResponse(
            id=device_id,
            fcm_token="masked_token",
            platform="android",
            device_id="device_002",
            created_at=now,
            updated_at=now,
        )

        # model_dump로 JSON 직렬화 가능
        data = response.model_dump()
        assert "id" in data
        assert data["fcm_token"] == "masked_token"
        assert data["platform"] == "android"

    def test_response_without_device_id(self):
        """device_id가 None인 응답"""
        from datetime import datetime
        from uuid import uuid4

        response = DeviceResponse(
            id=uuid4(),
            fcm_token="test_token",
            platform="ios",
            device_id=None,  # None 허용
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        assert response.device_id is None


class TestDeviceListResponse:
    """REQ-MOBILE-003: DeviceListResponse 스키마"""

    def test_empty_list(self):
        """빈 디바이스 목록"""
        response = DeviceListResponse(devices=[], total=0)
        assert response.devices == []
        assert response.total == 0

    def test_with_devices(self):
        """디바이스가 있는 목록"""
        from datetime import datetime
        from uuid import uuid4

        device = DeviceResponse(
            id=uuid4(),
            fcm_token="token1",
            platform="android",
            device_id="dev1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        response = DeviceListResponse(devices=[device], total=1)
        assert len(response.devices) == 1
        assert response.total == 1

    def test_multiple_devices(self):
        """여러 디바이스 목록"""
        from datetime import datetime
        from uuid import uuid4

        devices = [
            DeviceResponse(
                id=uuid4(),
                fcm_token=f"token{i}",
                platform="ios" if i % 2 == 0 else "android",
                device_id=f"dev{i}",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            for i in range(3)
        ]

        response = DeviceListResponse(devices=devices, total=3)
        assert len(response.devices) == 3
        assert response.total == 3

    def test_total_mismatch(self):
        """total 필드가 실제 디바이스 수와 다른 경우 (경계 조건)"""
        from datetime import datetime
        from uuid import uuid4

        device = DeviceResponse(
            id=uuid4(),
            fcm_token="token1",
            platform="ios",
            device_id="dev1",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )

        # total이 실제 수보다 많은 경우 (API 오류 시나리오)
        response = DeviceListResponse(devices=[device], total=5)
        assert len(response.devices) == 1
        assert response.total == 5  # total 필드는 독립적


# ---------------------------------------------------------------------------
# Push Service 테스트
# ---------------------------------------------------------------------------


class TestPushService:
    """REQ-MOBILE-004~006: PushService 기능 테스트"""

    def test_singleton_instance(self):
        """PushService 싱글톤 패턴"""
        from backend.services.push_service import get_push_service

        service1 = get_push_service()
        service2 = get_push_service()
        assert service1 is service2

    @pytest.mark.asyncio
    async def test_send_push_success(self):
        """REQ-MOBILE-004: 단일 푸시 전송 성공 (MOCK)"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        result = await service.send_push(
            token="test_token",
            title="Test Notification",
            body="Test body",
        )
        assert result is True  # MVP: 항상 성공

    @pytest.mark.asyncio
    async def test_send_push_with_data(self):
        """데이터 포함 푸시 전송"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        result = await service.send_push(
            token="test_token",
            title="Test",
            body="Body",
            data={"key": "value"},
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_multicast(self):
        """REQ-MOBILE-005: 멀티캐스트 푸시 전송"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        tokens = ["token1", "token2", "token3"]

        result = await service.send_multicast(
            tokens=tokens,
            title="Multicast Test",
            body="Sent to multiple devices",
        )

        assert result["success_count"] == 3
        assert result["failure_count"] == 0
        assert result["invalid_tokens"] == []

    @pytest.mark.asyncio
    async def test_send_multicast_empty_tokens(self):
        """빈 토큰 리스트 처리"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        result = await service.send_multicast(
            tokens=[],
            title="Test",
            body="Body",
        )

        assert result["success_count"] == 0
        assert result["failure_count"] == 0

    def test_register_device(self):
        """디바이스 등록 (인메모리)"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        service.register_device("device_001", "fcm_token_123")

        devices = service.get_all_devices()
        assert "device_001" in devices
        assert devices["device_001"] == "fcm_token_123"

    def test_unregister_device(self):
        """디바이스 등록 해제"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        service.register_device("device_001", "fcm_token_123")

        deleted = service.unregister_device("device_001")
        assert deleted is True

        # 삭제 후 존재하지 않음
        devices = service.get_all_devices()
        assert "device_001" not in devices

    def test_unregister_nonexistent_device(self):
        """존재하지 않는 디바이스 해제 시도"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        deleted = service.unregister_device("nonexistent")
        assert deleted is False

    def test_register_device_duplicate_token(self):
        """동일 device_id로 재등록 시 토큰 업데이트"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        service.register_device("device_001", "old_token")
        service.register_device("device_001", "new_token")

        devices = service.get_all_devices()
        assert devices["device_001"] == "new_token"

    def test_get_all_devices_returns_copy(self):
        """get_all_devices는 복사본을 반환하므로 원본 수정 불가"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        service.register_device("device_001", "token_001")

        devices = service.get_all_devices()
        original_count = len(devices)

        # 반환된 딕셔너리를 수정해도 원본에 영향 없음 (copy 사용)
        devices["device_002"] = "token_002"

        # 원본 저장소는 변화 없음
        all_devices = service.get_all_devices()
        assert len(all_devices) == original_count
        assert "device_002" not in all_devices

    def test_get_device_by_id(self):
        """특정 device_id로 디바이스 조회"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        service.register_device("device_001", "token_001")

        # get_all_devices를 통해 특정 디바이스 조회
        devices = service.get_all_devices()
        assert devices.get("device_001") == "token_001"
        assert devices.get("nonexistent") is None

    @pytest.mark.asyncio
    async def test_send_push_empty_title(self):
        """빈 제목으로 푸시 전송 (MVP: 허용됨)"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        result = await service.send_push(
            token="test_token",
            title="",  # 빈 제목
            body="Body text",
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_push_empty_body(self):
        """빈 본문으로 푸시 전송 (MVP: 허용됨)"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        result = await service.send_push(
            token="test_token",
            title="Title",
            body="",  # 빈 본문
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_multicast_with_data(self):
        """데이터 포함 멀티캐스트 전송"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        tokens = ["token1", "token2"]

        result = await service.send_multicast(
            tokens=tokens,
            title="Test",
            body="Body",
            data={"action": "open_screen", "screen": "chat"},
        )

        assert result["success_count"] == 2
        assert result["failure_count"] == 0

    @pytest.mark.asyncio
    async def test_send_multicast_single_token(self):
        """단일 토큰 멀티캐스트 전송"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        result = await service.send_multicast(
            tokens=["single_token"],
            title="Test",
            body="Body",
        )

        assert result["success_count"] == 1
        assert result["failure_count"] == 0


# ---------------------------------------------------------------------------
# Device API 엔드포인트 테스트
# ---------------------------------------------------------------------------


class TestDeviceAPIEndpoints:
    """Device API 엔드포인트 통합 테스트"""

    @pytest.fixture(autouse=True)
    def reset_push_service(self):
        """각 테스트 전에 PushService 상태 리셋"""
        from backend.services.push_service import get_push_service

        service = get_push_service()
        service._devices.clear()
        yield
        # 테스트 후 정리
        service._devices.clear()

    def test_register_device_success(self, client):
        """REQ-MOBILE-001: 디바이스 등록 성공"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_fcm_token_123",
                "platform": "ios",
                "device_id": "test_device_001",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert "id" in data
        assert data["fcm_token"] == "test_fcm_token_123"
        assert data["platform"] == "ios"
        assert data["device_id"] == "test_device_001"

    def test_register_device_without_device_id(self, client):
        """device_id 없이 등록 성공"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_fcm_token_456",
                "platform": "android",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["fcm_token"] == "test_fcm_token_456"
        assert data["platform"] == "android"

    def test_register_device_invalid_platform(self, client):
        """잘못된 플랫폼으로 등록 실패"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_token",
                "platform": "windows",  # 잘못된 플랫폼
            },
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_list_devices_empty(self, client):
        """REQ-MOBILE-003: 빈 디바이스 목록 조회"""
        response = client.get("/api/v1/devices/")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["devices"] == []
        assert data["total"] == 0

    def test_list_devices_after_register(self, client):
        """디바이스 등록 후 목록 조회"""
        # 먼저 디바이스 등록
        client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_token",
                "platform": "ios",
                "device_id": "device_list_test",
            },
        )

        # 목록 조회
        response = client.get("/api/v1/devices/")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["total"] == 1
        assert len(data["devices"]) == 1

    def test_unregister_device_success(self, client):
        """REQ-MOBILE-002: 디바이스 등록 해제 성공"""
        # 먼저 등록
        client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_token",
                "platform": "ios",
                "device_id": "device_to_delete",
            },
        )

        # 해제
        response = client.delete("/api/v1/devices/device_to_delete")
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # 해제 후 조회 불가
        response_get = client.get("/api/v1/devices/")
        data = response_get.json()
        deleted_device = [d for d in data["devices"] if d["device_id"] == "device_to_delete"]
        assert len(deleted_device) == 0

    def test_unregister_nonexistent_device(self, client):
        """존재하지 않는 디바이스 해제 실패"""
        response = client.delete("/api/v1/devices/nonexistent_device")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_register_device_missing_fcm_token(self, client):
        """FCM 토큰 누락으로 등록 실패"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "platform": "ios",
                # fcm_token 누락
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_device_invalid_platform_value(self, client):
        """잘못된 platform 값으로 등록 실패 (대소문자 구분)"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_token",
                "platform": "IOS",  # 대문자 (소문자만 허용)
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_device_empty_platform(self, client):
        """빈 platform 값으로 등록 실패"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_token",
                "platform": "",  # 빈 문자열
            },
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_register_duplicate_device_id(self, client):
        """동일 device_id로 재등록 시 업데이트됨"""
        # 첫 번째 등록
        response1 = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "first_token",
                "platform": "ios",
                "device_id": "duplicate_device",
            },
        )
        assert response1.status_code == status.HTTP_201_CREATED

        # 두 번째 등록 (같은 device_id)
        response2 = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "second_token",  # 다른 토큰
                "platform": "android",
                "device_id": "duplicate_device",
            },
        )
        assert response2.status_code == status.HTTP_201_CREATED

    def test_list_devices_pagination(self, client):
        """여러 디바이스 등록 후 목록 조회"""
        # 5개 디바이스 등록
        for i in range(5):
            client.post(
                "/api/v1/devices/register",
                json={
                    "fcm_token": f"token_{i}",
                    "platform": "ios",
                    "device_id": f"device_{i}",
                },
            )

        response = client.get("/api/v1/devices/")
        assert response.status_code == status.HTTP_200_OK

        data = response.json()
        assert data["total"] >= 5  # 이전 테스트의 디바이스 포함
        assert len(data["devices"]) >= 5

    def test_register_device_response_fields(self, client):
        """등록 응답에 필수 필드 포함 확인"""
        response = client.post(
            "/api/v1/devices/register",
            json={
                "fcm_token": "test_token",
                "platform": "android",
                "device_id": "field_check_device",
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()

        # 필수 필드 확인
        required_fields = ["id", "fcm_token", "platform", "device_id", "created_at", "updated_at"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
