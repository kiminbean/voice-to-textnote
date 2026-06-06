"""
OpenAI 클라이언트 단위 테스트
테스트 대상: backend.ml.openai_client.get_openai_client, get_cached_openai_client
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.ml.openai_client import get_cached_openai_client, get_openai_client

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_client():
    """테스트 간 전역 클라이언트 초기화"""
    from backend.ml import openai_client

    openai_client._openai_client = None
    yield
    openai_client._openai_client = None


# ---------------------------------------------------------------------------
# get_openai_client 테스트
# ---------------------------------------------------------------------------


class TestGetOpenAIClient:
    """get_openai_client 함수 테스트"""

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("backend.ml.openai_client.AsyncOpenAI")
    def test_returns_client_with_api_key(self, mock_async_openai):
        """API 키가 있을 때 클라이언트 반환 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        # Act
        result = get_openai_client()

        # Assert
        mock_async_openai.assert_called_once()
        call_kwargs = mock_async_openai.call_args[1]
        assert call_kwargs["api_key"] == "test-key"
        assert result == mock_client

    @patch.dict("os.environ", {}, clear=True)
    @patch("backend.ml.openai_client.AsyncOpenAI")
    def test_returns_dummy_client_without_api_key(self, mock_async_openai):
        """API 키가 없을 때 더미 클라이언트 반환 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        # Act
        result = get_openai_client()

        # Assert
        mock_async_openai.assert_called_once()
        call_kwargs = mock_async_openai.call_args[1]
        assert call_kwargs["api_key"] == "dummy-key"
        assert result == mock_client

    @patch.dict(
        "os.environ",
        {"OPENAI_API_KEY": "test-key", "OPENAI_BASE_URL": "https://custom.openai.com/v1"},
    )
    @patch("backend.ml.openai_client.AsyncOpenAI")
    def test_uses_custom_base_url(self, mock_async_openai):
        """커스텀 base_url 사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        # Act
        result = get_openai_client()

        # Assert
        mock_async_openai.assert_called_once()
        call_kwargs = mock_async_openai.call_args[1]
        assert call_kwargs["base_url"] == "https://custom.openai.com/v1"
        assert result == mock_client

    @patch.dict("os.environ", {}, clear=True)
    @patch("backend.ml.openai_client.AsyncOpenAI")
    def test_uses_default_base_url_without_api_key(self, mock_async_openai):
        """API 키 없을 때 기본 base_url 사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        # Act
        result = get_openai_client()

        # Assert
        mock_async_openai.assert_called_once()
        call_kwargs = mock_async_openai.call_args[1]
        assert call_kwargs["base_url"] == "https://api.openai.com/v1"
        assert result == mock_client

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("backend.ml.openai_client.AsyncOpenAI", side_effect=Exception("Connection error"))
    def test_returns_dummy_client_on_initialization_error(self, mock_async_openai):
        """초기화 실패 시 더미 클라이언트 반환 검증"""
        # Arrange
        with patch("backend.ml.openai_client.AsyncOpenAI") as mock_fallback:
            mock_fallback.return_value = MagicMock()

            # Act
            result = get_openai_client()

            # Assert
            # 첫 번째 호출은 실패, 두 번째는 더미 클라이언트 생성
            assert mock_fallback.call_count >= 1
            assert result is not None

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("backend.ml.openai_client.AsyncOpenAI")
    def test_uses_default_base_url_when_not_set(self, mock_async_openai):
        """base_url가 설정되지 않았을 때 기본값 사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_openai.return_value = mock_client

        # Act
        result = get_openai_client()

        # Assert
        mock_async_openai.assert_called_once()
        call_kwargs = mock_async_openai.call_args[1]
        assert call_kwargs["base_url"] == "https://api.openai.com/v1"
        assert result == mock_client


# ---------------------------------------------------------------------------
# get_cached_openai_client 테스트
# ---------------------------------------------------------------------------


class TestGetCachedOpenAIClient:
    """get_cached_openai_client 함수 테스트"""

    @patch("backend.ml.openai_client.get_openai_client")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_caches_client_on_first_call(self, mock_get_client):
        """첫 호출 시 클라이언트 캐싱 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Act
        result = get_cached_openai_client()

        # Assert
        mock_get_client.assert_called_once()
        assert result == mock_client
        from backend.ml import openai_client

        assert openai_client._openai_client is not None
        assert openai_client._openai_client == mock_client

    @patch("backend.ml.openai_client.get_openai_client")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_reuses_cached_client(self, mock_get_client):
        """이후 호출 시 캐시된 클라이언트 재사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Act - 첫 번째 호출
        result1 = get_cached_openai_client()

        # Act - 두 번째 호출
        result2 = get_cached_openai_client()

        # Assert
        assert mock_get_client.call_count == 1  # get_openai_client는 한 번만 호출
        assert result1 == mock_client
        assert result2 == mock_client
        assert result1 is result2  # 동일 인스턴스

    @patch("backend.ml.openai_client.get_openai_client")
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_global_client_state_persists(self, mock_get_client):
        """전역 클라이언트 상태 유지 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Act
        from backend.ml import openai_client

        # 초기 상태 확인
        assert openai_client._openai_client is None

        # 첫 번째 호출
        get_cached_openai_client()
        first_client = openai_client._openai_client

        # 두 번째 호출
        get_cached_openai_client()
        second_client = openai_client._openai_client

        # Assert
        assert first_client is not None
        assert second_client is not None
        assert first_client is second_client
