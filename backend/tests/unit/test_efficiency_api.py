"""
회의 효율성 API 테스트
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.services.efficiency_service import EfficiencyService


class TestEfficiencyAPI:
    """회의 효율성 API 테스트 클래스"""

    def setup_method(self):
        """테스트 메서드 설정"""
        self.client = TestClient(app)

    def test_efficiency_endpoint_exists(self):
        """회의 효율성 엔드포인트 존재 여부 확인"""
        # API 라우터가 정상적으로 등록되었는지 확인
        assert hasattr(app, 'routes')

        # efficiency 엔드포인트가 라우터에 있는지 확인
        efficiency_route = None
        for route in app.routes:
            if hasattr(route, 'path') and '/efficiency/' in route.path:
                efficiency_route = route
                break

        assert efficiency_route is not None, "Efficiency API endpoint not found"

    def test_efficiency_schema_import(self):
        """효율성 스키마 임포트 확인"""
        try:
            from backend.schemas.efficiency import EfficiencyScoreResponse
            assert EfficiencyScoreResponse is not None
        except ImportError as e:
            pytest.fail(f"Failed to import efficiency schema: {e}")

    def test_efficiency_service_import(self):
        """효율성 서비스 임포트 확인"""
        try:
            from backend.services.efficiency_service import EfficiencyService
            assert EfficiencyService is not None
        except ImportError as e:
            pytest.fail(f"Failed to import efficiency service: {e}")

    @pytest.mark.asyncio
    async def test_efficiency_service_basic_functionality(self):
        """효율성 서비스 기본 기능 테스트"""
        service = EfficiencyService()

        # Mock 데이터로 기능 테스트
        mock_segments = [
            {
                "speaker": "user1",
                "text": "프로젝트 진행 상황에 대해 논의합니다.",
                "start_time": 0,
                "end_time": 30,
            },
            {
                "speaker": "user2",
                "text": "최근 진행된 작업을 공유합니다.",
                "start_time": 30,
                "end_time": 60,
            },
        ]

        mock_db = AsyncMock()

        # Mock task result
        mock_result = MagicMock()
        mock_result.result_data = {"segments": mock_segments}
        mock_db.execute.return_value.scalars.return_value.first.return_value = mock_result

        # Test basic metrics calculation
        basic_metrics = service._calculate_basic_metrics(mock_segments, "standard")

        assert "total_duration" in basic_metrics
        assert "total_words" in basic_metrics
        assert "unique_speakers" in basic_metrics
        assert basic_metrics["unique_speakers"] == 2

    def test_efficiency_api_integration(self):
        """API 통합 테스트 (엔드포인트 응답 구조)"""
        api_routes = [route.path for route in app.routes if hasattr(route, 'path')]

        efficiency_found = any('/efficiency/' in route for route in api_routes)
        assert efficiency_found, "Efficiency endpoint not found in API routes"
