"""
SPEC-STATS-002: 전체 회의 통계 대시보드 API 테스트
"""

from backend.app.api.v1.analytics.dashboard import DashboardOverview


class TestDashboardOverview:
    def test_model_defaults(self):
        d = DashboardOverview(
            total_meetings=0,
            total_duration_seconds=0.0,
            avg_duration_seconds=0.0,
            total_words=0,
            total_segments=0,
            unique_speakers=0,
        )
        assert d.total_meetings == 0
        assert d.total_duration_seconds == 0.0

    def test_model_with_data(self):
        d = DashboardOverview(
            total_meetings=5,
            total_duration_seconds=1200.5,
            avg_duration_seconds=240.1,
            total_words=5000,
            total_segments=200,
            unique_speakers=8,
        )
        assert d.total_meetings == 5
        assert d.unique_speakers == 8
