"""
ZAIClient 클라이언트 단위 테스트
테스트 대상: backend.ml.zai_client.get_zai_client, get_cached_zai_client
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.ml.zai_client import (
    get_cached_zai_client,
    get_zai_client,
    structured_json_completion_options,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_client():
    """테스트 간 전역 클라이언트 초기화"""
    from backend.ml import zai_client

    zai_client._zai_client = None
    yield
    zai_client._zai_client = None


# ---------------------------------------------------------------------------
# get_zai_client 테스트
# ---------------------------------------------------------------------------


class TestGetZAIClient:
    """get_zai_client 함수 테스트"""

    @patch.dict("os.environ", {"ZAI_API_KEY": "test-key"}, clear=True)
    @patch("backend.ml.zai_client.AsyncZAIClient")
    def test_returns_client_with_api_key(self, mock_async_zai):
        """API 키가 있을 때 클라이언트 반환 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_zai.return_value = mock_client

        # Act
        result = get_zai_client()

        # Assert
        mock_async_zai.assert_called_once()
        call_kwargs = mock_async_zai.call_args[1]
        assert call_kwargs["api_key"] == "test-key"
        assert result == mock_client

    @patch.dict("os.environ", {}, clear=True)
    @patch("backend.ml.zai_client.AsyncZAIClient")
    def test_returns_dummy_client_without_api_key(self, mock_async_zai):
        """API 키가 없을 때 더미 클라이언트 반환 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_zai.return_value = mock_client

        # Act
        result = get_zai_client()

        # Assert
        mock_async_zai.assert_called_once()
        call_kwargs = mock_async_zai.call_args[1]
        assert call_kwargs["api_key"] == "dummy-key"
        assert result == mock_client

    @patch.dict(
        "os.environ",
        {"ZAI_API_KEY": "test-key", "ZAI_BASE_URL": "https://custom.zai.com/v1"},
    )
    @patch("backend.ml.zai_client.AsyncZAIClient")
    def test_uses_custom_base_url(self, mock_async_zai):
        """커스텀 base_url 사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_zai.return_value = mock_client

        # Act
        result = get_zai_client()

        # Assert
        mock_async_zai.assert_called_once()
        call_kwargs = mock_async_zai.call_args[1]
        assert call_kwargs["base_url"] == "https://custom.zai.com/v1"
        assert result == mock_client

    @patch.dict("os.environ", {}, clear=True)
    @patch("backend.ml.zai_client.AsyncZAIClient")
    def test_uses_default_base_url_without_api_key(self, mock_async_zai):
        """API 키 없을 때 기본 base_url 사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_zai.return_value = mock_client

        # Act
        result = get_zai_client()

        # Assert
        mock_async_zai.assert_called_once()
        call_kwargs = mock_async_zai.call_args[1]
        assert call_kwargs["base_url"] == "https://api.z.ai/api/coding/paas/v4"
        assert result == mock_client

    @patch.dict("os.environ", {"ZAI_API_KEY": "test-key"}, clear=True)
    @patch("backend.ml.zai_client.AsyncZAIClient", side_effect=Exception("Connection error"))
    def test_returns_dummy_client_on_initialization_error(self, mock_async_zai):
        """초기화 실패 시 더미 클라이언트 반환 검증"""
        # Arrange
        with patch("backend.ml.zai_client.AsyncZAIClient") as mock_fallback:
            mock_fallback.return_value = MagicMock()

            # Act
            result = get_zai_client()

            # Assert
            # 첫 번째 호출은 실패, 두 번째는 더미 클라이언트 생성
            assert mock_fallback.call_count >= 1
            assert result is not None

    @patch.dict("os.environ", {"ZAI_API_KEY": "test-key"}, clear=True)
    @patch("backend.ml.zai_client.AsyncZAIClient")
    def test_uses_default_base_url_when_not_set(self, mock_async_zai):
        """base_url가 설정되지 않았을 때 기본값 사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_async_zai.return_value = mock_client

        # Act
        result = get_zai_client()

        # Assert
        mock_async_zai.assert_called_once()
        call_kwargs = mock_async_zai.call_args[1]
        assert call_kwargs["base_url"] == "https://api.z.ai/api/coding/paas/v4"
        assert result == mock_client


class TestStructuredJsonCompletionOptions:
    """structured_json_completion_options 함수 테스트"""

    @patch.dict("os.environ", {"LLM_PROVIDER": "zai"}, clear=True)
    def test_disables_thinking_for_zai_glm_json_mode(self):
        options = structured_json_completion_options("glm-5.2")

        assert options["response_format"] == {"type": "json_object"}
        assert options["temperature"] == 0
        assert options["top_p"] == 0.01
        assert options["extra_body"] == {
            "thinking": {"type": "disabled"},
            "reasoning_effort": "none",
        }

    @patch.dict("os.environ", {"LLM_PROVIDER": "zai"}, clear=True)
    def test_keeps_plain_json_mode_for_non_glm_models(self):
        options = structured_json_completion_options("custom-json-model")

        assert options == {"response_format": {"type": "json_object"}}


# ---------------------------------------------------------------------------
# get_cached_zai_client 테스트
# ---------------------------------------------------------------------------


class TestGetCachedZAIClient:
    """get_cached_zai_client 함수 테스트"""

    @patch("backend.ml.zai_client.get_zai_client")
    @patch.dict("os.environ", {"ZAI_API_KEY": "test-key"})
    def test_caches_client_on_first_call(self, mock_get_client):
        """첫 호출 시 클라이언트 캐싱 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Act
        result = get_cached_zai_client()

        # Assert
        mock_get_client.assert_called_once()
        assert result == mock_client
        from backend.ml import zai_client

        assert zai_client._zai_client is not None
        assert zai_client._zai_client == mock_client

    @patch("backend.ml.zai_client.get_zai_client")
    @patch.dict("os.environ", {"ZAI_API_KEY": "test-key"})
    def test_reuses_cached_client(self, mock_get_client):
        """이후 호출 시 캐시된 클라이언트 재사용 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Act - 첫 번째 호출
        result1 = get_cached_zai_client()

        # Act - 두 번째 호출
        result2 = get_cached_zai_client()

        # Assert
        assert mock_get_client.call_count == 1  # get_zai_client는 한 번만 호출
        assert result1 == mock_client
        assert result2 == mock_client
        assert result1 is result2  # 동일 인스턴스

    @patch("backend.ml.zai_client.get_zai_client")
    @patch.dict("os.environ", {"ZAI_API_KEY": "test-key"})
    def test_global_client_state_persists(self, mock_get_client):
        """전역 클라이언트 상태 유지 검증"""
        # Arrange
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Act
        from backend.ml import zai_client

        # 초기 상태 확인
        assert zai_client._zai_client is None

        # 첫 번째 호출
        get_cached_zai_client()
        first_client = zai_client._zai_client

        # 두 번째 호출
        get_cached_zai_client()
        second_client = zai_client._zai_client

        # Assert
        assert first_client is not None
        assert second_client is not None
        assert first_client is second_client
