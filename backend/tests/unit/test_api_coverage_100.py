"""
Test Coverage 100% - 커버리지 100% 달성을 위한 테스트

각 파일별 커버되지 않은 라인을 타겟팅하여 100% 커버리지 달성
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.api.v1.auth.devices import is_valid_uuid
from backend.utils.validators import validate_webhook_url

# =============================================================================
# Auth API Tests (line 56)
# =============================================================================


class TestAuthAPI_GetAuthService:
    """auth.py line 56: get_auth_service 함수 테스트"""

    def test_get_auth_service_returns_instance(self):
        """get_auth_service는 AuthService 인스턴스를 반환해야 함"""
        from backend.app.api.v1.auth.auth import get_auth_service

        service = get_auth_service()
        assert service is not None
        assert hasattr(service, "register")
        assert hasattr(service, "login")
        assert hasattr(service, "refresh")


# =============================================================================
# Devices API Tests (line 145)
# =============================================================================


class TestDevicesAPI_IsValidUUID:
    """devices.py line 145: is_valid_uuid 함수 테스트"""

    def test_is_valid_uuid_with_valid_uuid(self):
        """유효한 UUID 문자열"""
        valid_uuid = str(uuid.uuid4())
        assert is_valid_uuid(valid_uuid) is True

    def test_is_valid_uuid_with_invalid_uuid(self):
        """유효하지 않은 UUID 문자열"""
        assert is_valid_uuid("not-a-uuid") is False
        assert is_valid_uuid("12345") is False
        assert is_valid_uuid("") is False


# =============================================================================
# Validators Tests (line 103+)
# =============================================================================


class TestValidators:
    """validators.py line 103+: webhook URL 검증"""

    def test_validate_webhook_url_with_private_ip(self):
        """사설 IP 주소로 webhook URL 거부"""
        with pytest.raises(ValueError, match="사설/로컬 네트워크"):
            validate_webhook_url("http://192.168.1.1/webhook", resolve_host=True)

    def test_validate_webhook_url_with_loopback(self):
        """루프백 주소로 webhook URL 거부"""
        with pytest.raises(ValueError, match="사설/로컬 네트워크"):
            validate_webhook_url("http://127.0.0.1/webhook", resolve_host=True)

    def test_validate_webhook_url_with_localhost(self):
        """localhost로 webhook URL 거부"""
        with pytest.raises(ValueError, match="localhost"):
            validate_webhook_url("http://localhost/webhook", resolve_host=True)

    def test_validate_webhook_url_with_credentials(self):
        """자격 증명 포함 webhook URL 거부"""
        with pytest.raises(ValueError, match="사용자 정보"):
            validate_webhook_url("http://user:pass@example.com/webhook")

    def test_validate_webhook_url_invalid_scheme(self):
        """잘못된 스킴으로 webhook URL 거부"""
        with pytest.raises(ValueError, match="HTTP\\(S\\)"):
            validate_webhook_url("ftp://example.com/webhook")

    def test_validate_webhook_url_success_public(self):
        """공개 URL로 webhook URL 검증 성공"""
        url = validate_webhook_url("https://example.com/webhook", resolve_host=False)
        assert url == "https://example.com/webhook"


# =============================================================================
# Pipeline Tests (lines 119, 409, 128, 146)
# =============================================================================


class TestDocxGenerator:
    """docx_generator.py line 119: DOCX 생성 실패"""

    def test_generate_docx_empty_segments(self):
        """빈 세그먼트로 DOCX 생성 시 ValueError"""
        from backend.pipeline.docx_generator import MinutesDOCXGenerator

        generator = MinutesDOCXGenerator()
        segments = []

        with pytest.raises(ValueError, match="유효한 segments"):
            generator.generate({"segments": segments})


class TestPdfGenerator:
    """pdf_generator.py line 409: PDF 생성 실패"""

    def test_generate_pdf_empty_content(self):
        """빈 내용으로 PDF 생성 시 ValueError"""
        from backend.pipeline.pdf_generator import MinutesPDFGenerator

        generator = MinutesPDFGenerator()
        # 빈 세그먼트로 ValueError 예상
        content = {"segments": []}

        with pytest.raises(ValueError, match="segments is empty"):
            generator.generate(content)


class TestMindMapGenerator:
    """mind_map_generator.py line 128: 마인드맵 생성 실패"""

    @patch("backend.pipeline.mind_map_generator.OpenAI")
    def test_generate_mind_map_empty_data(self, mock_openai):
        """빈 데이터로 마인드맵 생성"""
        from backend.pipeline.mind_map_generator import MindMapGenerator

        generator = MindMapGenerator()
        data = {}

        # OpenAI 응답 모킹
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"root": {"id": "root", "title": "Test"}}'
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.return_value = mock_client

        result = generator.generate_mind_map(
            summary_data=data, api_key="test_key", model="gpt-4", max_tokens=1000
        )
        assert result is not None


class TestStatisticsService:
    """services/statistics.py line 146: 통계 계산 실패"""

    @pytest.mark.asyncio
    async def test_fetch_minutes_result_not_found(self):
        """존재하지 않는 task_id로 조회 시 None 반환"""
        from backend.services.statistics import _fetch_minutes_result

        redis_mock = AsyncMock()
        redis_mock.get.return_value = None

        # DB mock 간소화
        class MockScalars:
            def first(self):
                return None

        class MockResult:
            def scalars(self):
                return MockScalars()

        class MockDB:
            async def execute(self, stmt):
                return MockResult()

        db_mock = MockDB()

        result = await _fetch_minutes_result(
            redis_client=redis_mock, db=db_mock, task_id="nonexistent-id"
        )

        assert result is None
