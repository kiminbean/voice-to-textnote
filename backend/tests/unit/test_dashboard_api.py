"""
대시보드 API 엔드포인트 테스트
SPEC-STATS-002: 전체 회의 통계 대시보드 API

엔드포인트:
- GET /api/v1/statistics/dashboard/overview
  전체 회의에 대한 종합 통계 (총 회의 수, 총 발화 시간, 평균 회의 길이, 상위 화자, 상위 키워드)
"""



class TestDashboardAPI:
    """대시보드 API 테스트 스위트"""

    def test_get_dashboard_overview_success(self, client):
        """
        대시보드 조회 성공 테스트
        Given: 완료된 회의 존재
        When: GET /api/v1/statistics/dashboard/overview
        Then: 200 OK와 통계 데이터 반환
        """
        # When
        response = client.get("/api/v1/statistics/dashboard/overview")

        # Then
        assert response.status_code == 200
        data = response.json()
        assert "total_meetings" in data
        assert "total_duration_seconds" in data
        assert "avg_duration_seconds" in data

    def test_get_dashboard_overview_with_limit(self, client):
        """
        limit 파라미터 포함 대시보드 조회 테스트
        Given: limit 파라미터
        When: GET /api/v1/statistics/dashboard/overview?limit=50
        Then: 200 OK
        """
        # When
        response = client.get("/api/v1/statistics/dashboard/overview?limit=50")

        # Then
        assert response.status_code == 200

    def test_get_dashboard_overview_invalid_limit(self, client):
        """
        잘못된 limit 파라미터 테스트
        Given: 범위를 벗어난 limit 값
        When: GET /api/v1/statistics/dashboard/overview?limit=1000
        Then: 422 Unprocessable Entity
        """
        # When - 범위 초과 (최대 500)
        response = client.get("/api/v1/statistics/dashboard/overview?limit=1000")

        # Then
        assert response.status_code == 422

    def test_get_dashboard_overview_invalid_limit_negative(self, client):
        """
        음수 limit 파라미터 테스트
        Given: 음수 limit 값
        When: GET /api/v1/statistics/dashboard/overview?limit=-1
        Then: 422 Unprocessable Entity
        """
        # When
        response = client.get("/api/v1/statistics/dashboard/overview?limit=-1")

        # Then
        assert response.status_code == 422

    def test_get_dashboard_overview_invalid_limit_zero(self, client):
        """
        0 limit 파라미터 테스트
        Given: 0 limit 값
        When: GET /api/v1/statistics/dashboard/overview?limit=0
        Then: 422 Unprocessable Entity
        """
        # When
        response = client.get("/api/v1/statistics/dashboard/overview?limit=0")

        # Then
        assert response.status_code == 422
