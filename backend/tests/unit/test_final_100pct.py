"""
Final push: main.py -> 100%, audit_log.py -> 100%, quality_service.py -> 100%

Uncovered lines:
- main.py line 127: logger.info after successful diarization model load
- audit_log.py line 57: existing counter returned from registry
- quality_service.py line 489: no relevant scores -> return 0.0
- quality_service.py line 560: LOW severity upgraded to MEDIUM
- quality_service.py line 611: grade "A"
- quality_service.py line 613: grade "B+"
- quality_service.py line 615: grade "B"
- quality_service.py line 621: grade "D"
- quality_service.py line 1028: trend direction "up"
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.quality_service import (
    IssueSeverity,
    QualityScore,
    QualityService,
)


# ---------------------------------------------------------------------------
# main.py - line 127
# ---------------------------------------------------------------------------
class TestMainFullCoverage:
    """Cover line 127: logger.info after successful diarization model preload."""

    @pytest.mark.asyncio
    async def test_diarization_model_preload_success(self):
        """Line 127: successful diarization model preload logs completion"""
        mock_dia = MagicMock()
        mock_stt = MagicMock()

        with patch("backend.app.main.validate_startup", new_callable=AsyncMock):
            with patch("backend.app.main.WhisperEngine", return_value=mock_stt):
                with patch("backend.app.main.DiarizationEngine", return_value=mock_dia):
                    with patch("backend.app.main.settings") as mock_settings:
                        mock_settings.whisper_model = "base"
                        mock_settings.huggingface_token = "hf_test_token"
                        mock_settings.diarization_model = "test-model"
                        with patch("backend.app.main.logger") as mock_logger:
                            # Import and call lifespan
                            from fastapi import FastAPI

                            from backend.app.main import lifespan

                            app = FastAPI()
                            async with lifespan(app):
                                pass  # Exit immediately

                            # Verify diarization load was called
                            mock_dia.load.assert_called_once()
                            # Verify success log was hit (line 127)
                            info_calls = [str(c) for c in mock_logger.info.call_args_list]
                            assert any("화자 분리 모델 사전 로드 완료" in c for c in info_calls)


# ---------------------------------------------------------------------------
# audit_log.py - line 57
# ---------------------------------------------------------------------------
class TestAuditLogFullCoverage:
    """Cover line 57: existing counter returned from registry."""

    def test_get_or_create_counter_returns_existing(self):
        """Line 57: _get_or_create_counter returns existing counter when already registered"""
        # Call once to create, then call again — second call should hit line 57

        from backend.app.middleware.audit_log import _get_or_create_counter

        # Create a counter with a unique test name
        test_name = "test_audit_log_coverage_counter"
        counter1 = _get_or_create_counter(test_name, "test doc", [])

        # Second call with same name should return existing (line 57)
        counter2 = _get_or_create_counter(test_name, "test doc", [])
        assert counter1 is counter2


# ---------------------------------------------------------------------------
# quality_service.py - lines 489, 560, 611, 613, 615, 621, 1028
# ---------------------------------------------------------------------------
class TestQualityServiceFullCoverage:
    # --- Line 489: _calculate_overall_score with no relevant scores ---
    def test_calculate_overall_score_no_basic_categories(self):
        """Line 489: return 0.0 when no relevant scores found"""
        service = QualityService()

        # Only non-basic category scores
        scores = [QualityScore(category="custom_metric", score=90.0, description="test")]

        result = service._calculate_overall_score(scores)
        assert result == 0.0

    # --- Line 560: LOW severity upgraded to MEDIUM when overall_score < 50 ---
    @pytest.mark.asyncio
    async def test_low_severity_upgraded_to_medium(self):
        """Line 560: LOW issues become MEDIUM when overall_score < 50"""
        service = QualityService()

        basic_analysis = {
            "has_attendees": False,
            "has_timeline": True,
            "has_action_items": True,
            "avg_sentence_length": 20,
        }
        ai_analysis = {"key_issues": []}

        # Patch IssueSeverity so HIGH becomes LOW in issue creation.
        # This makes the "no attendees" issue (normally HIGH) created as LOW,
        # then the upgrade loop hits `elif severity == LOW: severity = MEDIUM`
        import backend.services.quality_service as qs_mod

        mock_severity = MagicMock()
        mock_severity.HIGH = IssueSeverity.LOW  # Issues created as "HIGH" -> actually LOW
        mock_severity.MEDIUM = IssueSeverity.MEDIUM
        mock_severity.LOW = IssueSeverity.LOW
        mock_severity.CRITICAL = IssueSeverity.CRITICAL

        with patch.object(qs_mod, "IssueSeverity", mock_severity):
            issues = await service._identify_issues(
                basic_analysis=basic_analysis,
                ai_analysis=ai_analysis,
                overall_score=30.0,
            )

            # The issue created with mock HIGH (actually LOW) should be upgraded to MEDIUM
            assert any(i.severity == IssueSeverity.MEDIUM for i in issues)

    # --- Lines 611, 613, 615, 621: _calculate_grade edge cases ---
    def test_calculate_grade_a(self):
        """Line 611: grade A for score 85-89"""
        service = QualityService()
        assert service._calculate_grade(87.0) == "A"

    def test_calculate_grade_b_plus(self):
        """Line 613: grade B+ for score 80-84"""
        service = QualityService()
        assert service._calculate_grade(82.0) == "B+"

    def test_calculate_grade_b(self):
        """Line 615: grade B for score 75-79"""
        service = QualityService()
        assert service._calculate_grade(77.0) == "B"

    def test_calculate_grade_d(self):
        """Line 621: grade D for score 60-64"""
        service = QualityService()
        assert service._calculate_grade(62.0) == "D"

    def test_calculate_grade_all_boundaries(self):
        """Verify all grade boundaries work correctly"""
        service = QualityService()
        assert service._calculate_grade(95.0) == "A+"
        assert service._calculate_grade(90.0) == "A+"
        assert service._calculate_grade(89.0) == "A"
        assert service._calculate_grade(85.0) == "A"
        assert service._calculate_grade(84.0) == "B+"
        assert service._calculate_grade(80.0) == "B+"
        assert service._calculate_grade(79.0) == "B"
        assert service._calculate_grade(75.0) == "B"
        assert service._calculate_grade(74.0) == "C+"
        assert service._calculate_grade(70.0) == "C+"
        assert service._calculate_grade(69.0) == "C"
        assert service._calculate_grade(65.0) == "C"
        assert service._calculate_grade(64.0) == "D"
        assert service._calculate_grade(60.0) == "D"
        assert service._calculate_grade(59.0) == "F"
        assert service._calculate_grade(0.0) == "F"

    # --- Line 1028: trend direction "up" when delta > 2.0 ---
    @pytest.mark.asyncio
    async def test_trend_direction_up(self):
        """Line 1028: direction = 'up' when second half scores are much higher"""
        service = QualityService()

        # Create snapshots with increasing scores (upward trend)
        snapshots = []
        for i in range(6):
            snap = MagicMock()
            snap.created_at = datetime.now(UTC) + timedelta(hours=i)
            snap.overall_score = 60.0 + (i * 5)  # 60, 65, 70, 75, 80, 85
            snap.grade = "B"
            snap.mode = "completeness"
            snapshots.append(snap)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = snapshots

        db = AsyncMock()
        db.execute.return_value = mock_result

        with patch("os.getenv", return_value="10"):
            result = await service.get_quality_trends(db, task_id="test-task")

            assert result.trend_direction == "up"
            assert result.points_count == 6
