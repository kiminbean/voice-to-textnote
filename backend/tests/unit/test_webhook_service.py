"""
WebhookService 단위 테스트
SPEC-WEBHOOK-001: 웹훅 엔드포인트 CRUD 서비스
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.db.webhook_models import WebhookEndpoint
from backend.db.webhook_service import WebhookService
from backend.schemas.webhook import WebhookEndpointCreate, WebhookEndpointUpdate


@pytest.fixture
def webhook_service():
    """WebhookService 인스턴스 fixture"""
    return WebhookService()


@pytest.fixture
def mock_session():
    """AsyncSession mock fixture"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def sample_user_id():
    """테스트용 사용자 ID"""
    return uuid.uuid4()


@pytest.fixture
def sample_webhook_id():
    """테스트용 웹훅 ID"""
    return uuid.uuid4()


@pytest.fixture
def sample_webhook_create_payload():
    """웹훅 생성 payload"""
    return WebhookEndpointCreate(
        url="https://example.com/webhook",
        events=["transcription.completed"],
        secret="test_secret",
        description="Test webhook"
    )


@pytest.fixture
def sample_webhook_update_payload():
    """웹훅 수정 payload"""
    return WebhookEndpointUpdate(
        url="https://example.com/updated",
        is_active=False
    )


@pytest.fixture
def sample_webhook_endpoint(sample_user_id, sample_webhook_id):
    """WebhookEndpoint ORM 객체 mock"""
    webhook = MagicMock(spec=WebhookEndpoint)
    webhook.id = sample_webhook_id
    webhook.user_id = sample_user_id
    webhook.url = "https://example.com/webhook"
    webhook.events = ["transcription.completed"]
    webhook.secret = "test_secret"
    webhook.is_active = True
    webhook.description = "Test webhook"
    webhook.created_at = datetime.now(UTC)
    webhook.updated_at = datetime.now(UTC)
    return webhook


# _enforce_user_limit 테스트

class TestEnforceUserLimit:
    """_enforce_user_limit 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_under_limit_passes(self, webhook_service, mock_session, sample_user_id):
        """웹훅 개수가 제한 미만인 경우 통과"""
        # Setup: count = 5 (< 20)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 5
        mock_session.execute.return_value = mock_result

        # Execute
        await webhook_service._enforce_user_limit(mock_session, sample_user_id)

        # Assert: 예외 없이 통과
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_at_limit_fails(self, webhook_service, mock_session, sample_user_id):
        """웹훅 개수가 제한과 같은 경우도 예외 발생"""
        # Setup: count = 20
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 20
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await webhook_service._enforce_user_limit(mock_session, sample_user_id)

        assert exc_info.value.status_code == 409
        assert "최대 20개까지" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_over_limit_raises(self, webhook_service, mock_session, sample_user_id):
        """웹훅 개수가 제한 초과인 경우 409 예외 발생"""
        # Setup: count = 21 (> 20)
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 21
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await webhook_service._enforce_user_limit(mock_session, sample_user_id)

        assert exc_info.value.status_code == 409
        assert "최대 20개까지" in exc_info.value.detail


# create 테스트

class TestCreate:
    """create 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_create_success(
        self, webhook_service, mock_session, sample_user_id, sample_webhook_create_payload
    ):
        """웹훅 생성 성공"""
        # Setup: _enforce_user_limit 통과, user_id 확인
        with patch.object(webhook_service, "_enforce_user_limit", AsyncMock()):
            # Execute
            result = await webhook_service.create(
                mock_session, sample_user_id, sample_webhook_create_payload
            )

            # Assert: session.add 및 commit 호출
            mock_session.add.assert_called_once()
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()
            assert isinstance(result, WebhookEndpoint)

    @pytest.mark.asyncio
    async def test_create_enforces_limit(
        self, webhook_service, mock_session, sample_user_id, sample_webhook_create_payload
    ):
        """웹훅 생성 시 사용자 제한 확인"""
        # Setup: _enforce_user_limit 예외 발생
        with patch.object(
            webhook_service, "_enforce_user_limit", AsyncMock(side_effect=Exception("Limit exceeded"))
        ):
            # Execute & Assert
            with pytest.raises(Exception, match="Limit exceeded"):
                await webhook_service.create(
                    mock_session, sample_user_id, sample_webhook_create_payload
                )


# get_by_id 테스트

class TestGetById:
    """get_by_id 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_get_found(self, webhook_service, mock_session, sample_webhook_endpoint):
        """웹훅 조회 성공"""
        # Setup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_webhook_endpoint
        mock_session.execute.return_value = mock_result

        # Execute
        result = await webhook_service.get_by_id(
            mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
        )

        # Assert
        assert result == sample_webhook_endpoint

    @pytest.mark.asyncio
    async def test_get_not_found(self, webhook_service, mock_session, sample_webhook_id, sample_user_id):
        """웹훅 조회 실패 - 존재하지 않음"""
        # Setup: None 반환
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Execute & Assert
        with pytest.raises(Exception) as exc_info:
            await webhook_service.get_by_id(mock_session, sample_webhook_id, sample_user_id)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_wrong_user(self, webhook_service, mock_session, sample_webhook_endpoint):
        """웹훅 조회 실패 - 사용자 불일치"""
        # Setup
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_webhook_endpoint
        mock_session.execute.return_value = mock_result

        # Execute & Assert (다른 사용자 ID로 조회)
        with pytest.raises(Exception) as exc_info:
            await webhook_service.get_by_id(
                mock_session, sample_webhook_endpoint.id, uuid.uuid4()
            )

        assert exc_info.value.status_code == 404


# list_for_user 테스트

class TestListForUser:
    """list_for_user 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_list_success(self, webhook_service, mock_session, sample_user_id):
        """웹훅 목록 조회 성공"""
        # Setup
        mock_webhooks = [MagicMock(spec=WebhookEndpoint) for _ in range(3)]

        # count 쿼리 mock
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 3

        # list 쿼리 mock
        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = mock_webhooks

        # execute가 순서대로 두 번 호출되도록 설정
        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        # Execute
        items, total = await webhook_service.list_for_user(mock_session, sample_user_id, limit=10, offset=0)

        # Assert
        assert items == mock_webhooks
        assert total == 3
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_list_empty(self, webhook_service, mock_session, sample_user_id):
        """빈 웹훅 목록 조회"""
        # Setup
        mock_count_result = MagicMock()
        mock_count_result.scalar_one.return_value = 0

        mock_list_result = MagicMock()
        mock_list_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [mock_count_result, mock_list_result]

        # Execute
        items, total = await webhook_service.list_for_user(mock_session, sample_user_id, limit=10, offset=0)

        # Assert
        assert items == []
        assert total == 0


# update 테스트

class TestUpdate:
    """update 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_update_partial(
        self,
        webhook_service,
        mock_session,
        sample_webhook_endpoint,
        sample_webhook_update_payload,
    ):
        """웹훅 부분 업데이트 성공"""
        # Setup: get_by_id가 endpoint를 반환하도록 mock
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            # Execute
            result = await webhook_service.update(
                mock_session,
                sample_webhook_endpoint.id,
                sample_webhook_endpoint.user_id,
                sample_webhook_update_payload,
            )

            # Assert
            assert result.url == sample_webhook_update_payload.url
            assert result.is_active == sample_webhook_update_payload.is_active
            mock_session.commit.assert_called_once()
            mock_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_no_changes(self, webhook_service, mock_session, sample_webhook_endpoint):
        """업데이트할 필드가 없는 경우"""
        # Setup: 빈 payload
        payload = WebhookEndpointUpdate()

        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            # Execute
            result = await webhook_service.update(
                mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id, payload
            )

            # Assert: 변경 없지만 commit은 호출됨
            mock_session.commit.assert_called_once()
            assert result == sample_webhook_endpoint


# delete 테스트

class TestDelete:
    """delete 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_delete_success(self, webhook_service, mock_session, sample_webhook_endpoint):
        """웹훅 삭제 성공"""
        # Setup: get_by_id가 endpoint를 반환
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            # Execute
            await webhook_service.delete(
                mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
            )

            # Assert
            mock_session.delete.assert_called_once_with(sample_webhook_endpoint)
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_not_found(self, webhook_service, mock_session, sample_webhook_id, sample_user_id):
        """존재하지 않는 웹훅 삭제 시도"""
        # Setup: get_by_id가 404 예외 발생
        from fastapi import HTTPException

        http_exc = HTTPException(status_code=404, detail="Not found")

        with patch.object(
            webhook_service, "get_by_id", AsyncMock(side_effect=http_exc)
        ):
            # Execute & Assert
            with pytest.raises(HTTPException) as exc_info:
                await webhook_service.delete(mock_session, sample_webhook_id, sample_user_id)

            assert exc_info.value.status_code == 404


# ping 테스트

class TestPing:
    """ping 메서드 테스트"""

    @pytest.mark.asyncio
    async def test_ping_success(self, webhook_service, mock_session, sample_webhook_endpoint):
        """핑 전송 성공 (200 OK)"""
        # Setup
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_cls.return_value = mock_client

                with patch("backend.db.webhook_service.validate_webhook_url", return_value="https://example.com/webhook"):
                    # Execute
                    status, success, message = await webhook_service.ping(
                        mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
                    )

                    # Assert
                    assert status == 200
                    assert success is True
                    assert "성공" in message

    @pytest.mark.asyncio
    async def test_ping_with_secret(self, webhook_service, mock_session, sample_webhook_endpoint):
        """시크릿 포함 핑 전송 (서명 헤더 확인)"""
        # Setup
        sample_webhook_endpoint.secret = "test_secret_key"

        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_cls.return_value = mock_client

                with patch("backend.db.webhook_service.validate_webhook_url", return_value="https://example.com/webhook"):
                    # Execute
                    status, success, message = await webhook_service.ping(
                        mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
                    )

                    # Assert: 서명 헤더가 포함되어야 함
                    assert success is True
                    # post 호출이 한 번 이상 호출되었는지 확인
                    assert mock_client.post.call_count >= 1

    @pytest.mark.asyncio
    async def test_ping_http_error(self, webhook_service, mock_session, sample_webhook_endpoint):
        """핑 전송 실패 (HTTP 400)"""
        # Setup
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            mock_response = MagicMock()
            mock_response.status_code = 400

            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_cls.return_value = mock_client

                with patch("backend.db.webhook_service.validate_webhook_url", return_value="https://example.com/webhook"):
                    # Execute
                    status, success, message = await webhook_service.ping(
                        mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
                    )

                    # Assert
                    assert status == 400
                    assert success is False
                    assert "400" in message

    @pytest.mark.asyncio
    async def test_ping_timeout(self, webhook_service, mock_session, sample_webhook_endpoint):
        """핑 전송 타임아웃"""
        # Setup
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.side_effect = httpx.TimeoutException("Timeout")
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_cls.return_value = mock_client

                with patch("backend.db.webhook_service.validate_webhook_url", return_value="https://example.com/webhook"):
                    # Execute
                    status, success, message = await webhook_service.ping(
                        mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
                    )

                    # Assert
                    assert status is None
                    assert success is False
                    assert "타임아웃" in message

    @pytest.mark.asyncio
    async def test_ping_connection_error(self, webhook_service, mock_session, sample_webhook_endpoint):
        """핑 전송 연결 오류"""
        # Setup
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            with patch("httpx.AsyncClient") as mock_client_cls:
                mock_client = AsyncMock()
                mock_client.post.side_effect = Exception("Connection refused")
                mock_client.__aenter__.return_value = mock_client
                mock_client.__aexit__.return_value = None
                mock_client_cls.return_value = mock_client

                with patch("backend.db.webhook_service.validate_webhook_url", return_value="https://example.com/webhook"):
                    # Execute
                    status, success, message = await webhook_service.ping(
                        mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
                    )

                    # Assert
                    assert status is None
                    assert success is False
                    assert "연결 오류" in message

    @pytest.mark.asyncio
    async def test_ping_invalid_url(self, webhook_service, mock_session, sample_webhook_endpoint):
        """잘못된 URL로 핑 전송 시도"""
        # Setup
        with patch.object(
            webhook_service, "get_by_id", AsyncMock(return_value=sample_webhook_endpoint)
        ):
            with patch("backend.db.webhook_service.validate_webhook_url", side_effect=ValueError("Invalid URL")):
                # Execute
                status, success, message = await webhook_service.ping(
                    mock_session, sample_webhook_endpoint.id, sample_webhook_endpoint.user_id
                )

                # Assert
                assert status is None
                assert success is False
                assert "Invalid URL" in message
