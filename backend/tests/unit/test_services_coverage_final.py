"""
Services Coverage Final Test Suite
Tests for uncovered lines in backend service files

Files covered:
- backend/services/enhanced_statistics.py (93% -> target 95%+)
- backend/services/retention.py (93% -> target 95%+)
- backend/services/oauth_service.py (95% -> target 95%+)
- backend/services/quality_service.py (95% -> target 95%+)
- backend/services/keyword_service.py (96% -> target 95%+)
- backend/services/statistics.py (96% -> target 95%+)
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.enhanced_statistics import (
    EfficiencyMetrics,
    EnhancedStatisticsService,
    KeywordTrend,
    SpeakerParticipationPattern,
    TimeSeriesDataPoint,
)
from backend.services.keyword_service import (
    KeywordResponse,
    KeywordService,
)
from backend.services.oauth_service import verify_apple_token
from backend.services.quality_service import (
    IssueSeverity,
    QualityService,
    QualityTrendsResponse,
)
from backend.services.retention import cleanup_temp_files
from backend.services.statistics import StatisticsService


# ---------------------------------------------------------------------------
# EnhancedStatistics
# ---------------------------------------------------------------------------
class TestEnhancedStatisticsCoverage:
    """Tests for enhanced_statistics.py uncovered lines"""

    def test_time_series_with_invalid_segment_types(self):
        """Test _generate_time_series with non-dict segments (line 299)"""
        service = EnhancedStatisticsService()

        # Use timestamps in different hours so they land in different buckets
        segments = [
            {"start": 0.0, "end": 5.0, "text": "valid segment"},
            "invalid_string_segment",  # Line 299: continue
            None,  # Line 299: continue
            {"start": 7200.0, "end": 7205.0, "text": "another valid"},  # 2 hours later
        ]

        result = service._generate_time_series(segments, time_range="1d")

        # Should only process valid dict segments
        assert len(result) == 2
        assert all(isinstance(point, TimeSeriesDataPoint) for point in result)

    def test_time_series_with_invalid_timestamp_values(self):
        """Test _generate_time_series with invalid timestamp values (lines 304-305)"""
        service = EnhancedStatisticsService()

        segments = [
            {"start": "invalid", "end": 5.0},  # ValueError caught
            {"start": 0.0, "end": "invalid"},  # ValueError caught
            {"start": None, "end": 5.0},  # TypeError caught
            {"start": 0.0, "end": 10.0, "text": "valid"},
        ]

        result = service._generate_time_series(segments, time_range="1d")
        assert len(result) == 1

    def test_speaker_patterns_with_non_dict_segments(self):
        """Test _analyze_speaker_patterns skips non-dict segments (line 345)"""
        service = EnhancedStatisticsService()

        segments = [
            {"speaker": "A", "start": 0.0, "end": 5.0, "text": "valid"},
            "invalid_string",
            None,
            {"speaker": "B", "start": 6.0, "end": 10.0, "text": "also valid"},
        ]

        result = service._analyze_speaker_patterns(segments)
        assert len(result) == 2
        assert all(isinstance(pattern, SpeakerParticipationPattern) for pattern in result)

    def test_speaker_patterns_with_invalid_timestamps(self):
        """Test _analyze_speaker_patterns with invalid timestamps (lines 352-353)"""
        service = EnhancedStatisticsService()

        segments = [
            {"speaker": "A", "start": "bad", "end": 5.0},  # ValueError -> continue
            {"speaker": "B", "start": 0.0, "end": 5.0, "text": "valid"},
        ]

        result = service._analyze_speaker_patterns(segments)
        assert len(result) == 1
        assert result[0].speaker == "B"

    def test_keyword_trends_with_non_dict_segments(self):
        """Test _analyze_keyword_trends skips non-dict segments (line 424)"""
        service = EnhancedStatisticsService()

        segments = [
            {"text": "keyword test", "start": 0.0},
            "invalid_segment",
            None,
            {"text": "another keyword", "start": 5.0},
        ]

        result = service._analyze_keyword_trends(segments, top_n=5)
        assert isinstance(result, list)
        assert all(isinstance(item, KeywordTrend) for item in result)

    def test_keyword_trends_with_invalid_start_values(self):
        """Test _analyze_keyword_trends with invalid start values (lines 429-430)"""
        service = EnhancedStatisticsService()

        segments = [
            {"text": "test", "start": "invalid"},  # Line 429-430: continue
            {"text": "valid", "start": 0.0},
        ]

        result = service._analyze_keyword_trends(segments, top_n=5)
        assert isinstance(result, list)

    def test_keyword_trends_single_appearance_frequency(self):
        """Test _analyze_keyword_trends with single appearance (line 467)"""
        service = EnhancedStatisticsService()

        segments = [
            {"text": "unique keyword", "start": 0.0},
        ]

        result = service._analyze_keyword_trends(segments, top_n=10)
        if result:
            trend = next((t for t in result if t.keyword == "unique"), None)
            if trend:
                assert isinstance(trend.frequency_change, float)

    def test_efficiency_metrics_non_dict_segments(self):
        """Test _calculate_efficiency_metrics skips non-dict segments (line 513)"""
        service = EnhancedStatisticsService()

        segments = [
            {"speaker": "A", "start": 0.0, "end": 5.0},
            "invalid",
            None,
        ]

        result = service._calculate_efficiency_metrics(segments)
        assert isinstance(result, EfficiencyMetrics)
        assert result.total_duration_seconds == 5.0

    def test_efficiency_metrics_invalid_timestamps(self):
        """Test _calculate_efficiency_metrics with invalid timestamps (lines 518-519)"""
        service = EnhancedStatisticsService()

        segments = [
            {"speaker": "A", "start": "bad", "end": 5.0},
            {"speaker": "B", "start": 0.0, "end": 5.0},
        ]

        result = service._calculate_efficiency_metrics(segments)
        assert result.total_duration_seconds == 5.0

    def test_participation_balance_empty_speaker_durations(self):
        """Test _calculate_efficiency_metrics with no speakers (line 550)"""
        service = EnhancedStatisticsService()
        result = service._calculate_efficiency_metrics([])
        assert result.participation_balance == 0.0

    def test_efficiency_score_turn_length_too_short(self):
        """Test _calculate_efficiency_score with short turns (line 581-582)"""
        service = EnhancedStatisticsService()

        segments = [
            {"speaker": "A", "start": 0.0, "end": 10.0},
            {"speaker": "B", "start": 10.0, "end": 20.0},
        ]

        result = service._calculate_efficiency_score(segments)
        assert 0.0 <= result <= 1.0

    def test_efficiency_score_turn_length_too_long(self):
        """Test _calculate_efficiency_score with long turns (line 584)"""
        service = EnhancedStatisticsService()

        segments = [
            {"speaker": "A", "start": 0.0, "end": 200.0},
        ]

        result = service._calculate_efficiency_score(segments)
        assert 0.0 <= result <= 1.0


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------
class TestRetentionCoverage:
    """Tests for retention.py uncovered lines (lines 82-88)"""

    def test_cleanup_temp_files_handles_file_not_found(self, tmp_path: Path):
        """Test cleanup_temp_files handles FileNotFoundError (lines 80-81)"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        # 전역 Path.stat patch 대신, 실제 파일의 stat()만 mock하여 FileNotFoundError 유발
        # temp_dir.exists()는 정상 작동해야 하므로 전역 patch는 제거
        original_stat = Path.stat

        def mock_stat_fn(self, follow_symlinks=True):
            # test_file에 대해서만 FileNotFoundError, 나머지는 원본 동작
            if self == test_file:
                raise FileNotFoundError()
            return original_stat(self, follow_symlinks=follow_symlinks)  # pragma: no cover

        with patch.object(Path, "stat", mock_stat_fn):
            with patch("backend.services.retention.logger"):
                deleted_count, freed_bytes = cleanup_temp_files(tmp_path, retention_hours=1)
                assert deleted_count == 0
                assert freed_bytes == 0

    def test_cleanup_temp_files_handles_os_error(self, tmp_path: Path):
        """Test cleanup_temp_files handles OSError (lines 82-88)"""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        stat_result = MagicMock()
        stat_result.st_size = 1024
        stat_result.st_mtime = 100

        with patch("pathlib.Path.stat", return_value=stat_result):
            with patch("pathlib.Path.is_file", return_value=True):
                with patch("pathlib.Path.unlink", side_effect=OSError("Permission denied")):
                    with patch("backend.services.retention.logger") as mock_logger:
                        result = cleanup_temp_files(tmp_path, retention_hours=1)
                        assert result[0] == 0
                        assert mock_logger.warning.called


# ---------------------------------------------------------------------------
# OAuthService
# ---------------------------------------------------------------------------
class TestOAuthServiceCoverage:
    """Tests for oauth_service.py uncovered lines"""

    @pytest.mark.asyncio
    async def test_apple_auth_missing_kid_in_token(self):
        """Test Apple auth with missing kid in token (line 118)"""
        # oauth_service uses: from jose import JWTError, jwt
        with patch("backend.services.oauth_service.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {}

            with patch("backend.services.oauth_service.settings") as mock_settings:
                mock_settings.apple_client_id = "test-client-id"
                mock_settings.apple_team_id = "test-team-id"

                with pytest.raises(ValueError, match="kid"):
                    await verify_apple_token("fake_token")

    @pytest.mark.asyncio
    async def test_apple_auth_public_key_not_found(self):
        """Test Apple auth when public key not found (line 127)"""
        with patch("backend.services.oauth_service.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "unknown-key"}

            with patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client:
                mock_response = MagicMock()
                mock_response.json.return_value = {"keys": [{"kid": "other-key"}]}
                mock_response.raise_for_status = MagicMock()
                mock_client.return_value.__aenter__.return_value.get.return_value = mock_response

                with patch("backend.services.oauth_service.settings") as mock_settings:
                    mock_settings.apple_client_id = "test-client-id"
                    mock_settings.apple_team_id = "test-team-id"

                    with pytest.raises(ValueError, match="공개 키"):
                        await verify_apple_token("fake_token")

    @pytest.mark.asyncio
    async def test_apple_auth_jwt_decode_error(self):
        """Test Apple auth with JWT decode error (lines 137-138)"""
        with patch("backend.services.oauth_service.jwt") as mock_jwt:
            mock_jwt.get_unverified_header.return_value = {"kid": "test-key"}
            mock_jwt.decode.side_effect = Exception("Invalid token")

            with patch("backend.services.oauth_service.JWTError", Exception):
                with patch("backend.services.oauth_service.httpx.AsyncClient") as mock_client:
                    mock_response = MagicMock()
                    mock_response.json.return_value = {
                        "keys": [{"kid": "test-key", "n": "test", "e": "AQAB"}]
                    }
                    mock_response.raise_for_status = MagicMock()
                    mock_client.return_value.__aenter__.return_value.get.return_value = (
                        mock_response
                    )

                    with patch("backend.services.oauth_service.settings") as mock_settings:
                        mock_settings.apple_client_id = "test-client-id"
                        mock_settings.apple_team_id = "test-team-id"

                        with pytest.raises(ValueError, match="Apple ID token 검증 실패"):
                            await verify_apple_token("fake_token")


# ---------------------------------------------------------------------------
# QualityService
# ---------------------------------------------------------------------------
class TestQualityServiceCoverage:
    """Tests for quality_service.py uncovered lines"""

    @pytest.mark.asyncio
    async def test_assess_minutes_exception_handling(self):
        """Test assess_minutes exception handling (lines 140-142)"""
        service = QualityService()

        with patch.object(service, "_perform_basic_analysis", side_effect=RuntimeError("DB Error")):
            with patch("backend.services.quality_service.logger") as mock_logger:
                with pytest.raises(RuntimeError, match="DB Error"):
                    await service.assess_minutes(
                        task_id="test-task",
                        meeting_content="test content",
                        meeting_title="Test Meeting",
                    )
                assert mock_logger.error.called

    @pytest.mark.asyncio
    async def test_basic_analysis_regex_patterns(self):
        """Test _perform_basic_analysis regex patterns (lines 150-151)"""
        service = QualityService()

        content = "Hello World! This is a test. Another sentence."
        result = await service._perform_basic_analysis(content)

        assert "sentence_count" in result
        assert result["sentence_count"] > 0

    @pytest.mark.asyncio
    async def test_ai_assessment_json_extraction(self):
        """Test _ai_based_assessment JSON extraction (lines 221-231)"""
        service = QualityService()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[
            0
        ].message.content = 'Some text before\n{"score": 85}\nSome text after'
        service.openai_client = MagicMock()
        service.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await service._ai_based_assessment(
            "test content", "Test Title", assessment_focus=[]
        )

        assert isinstance(result, dict)
        assert "score" in result

    @pytest.mark.asyncio
    async def test_ai_assessment_json_parse_failure(self):
        """Test _ai_based_assessment JSON parse failure (lines 230-231)"""
        service = QualityService()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "No JSON here, just text"
        service.openai_client = MagicMock()
        service.openai_client.chat.completions.create = AsyncMock(return_value=mock_response)

        result = await service._ai_based_assessment(
            "test content", "Test Title", assessment_focus=[]
        )

        assert isinstance(result, dict)
        assert "completeness_score" in result

    @pytest.mark.asyncio
    async def test_identify_issues_from_ai_analysis(self):
        """Test _identify_issues from AI analysis (lines 489-560)"""
        service = QualityService()

        basic_analysis = {
            "has_attendees": True,
            "has_timeline": True,
            "has_action_items": True,
            "avg_sentence_length": 20,
        }
        ai_analysis = {
            "key_issues": ["Issue 1", "Issue 2"],
        }

        issues = await service._identify_issues(
            basic_analysis=basic_analysis,
            ai_analysis=ai_analysis,
            overall_score=60.0,
        )

        assert len(issues) >= 2
        assert any(issue.category == "ai_analysis" for issue in issues)

    @pytest.mark.asyncio
    async def test_issue_severity_upgrade_for_low_score(self):
        """Test _identify_issues severity upgrade (lines 555-560)"""
        service = QualityService()

        basic_analysis = {
            "has_attendees": True,
            "has_timeline": False,  # Creates MEDIUM issue -> upgraded to HIGH
            "has_action_items": True,
            "avg_sentence_length": 20,
        }
        ai_analysis = {"key_issues": []}

        issues = await service._identify_issues(
            basic_analysis=basic_analysis,
            ai_analysis=ai_analysis,
            overall_score=45.0,  # Below 50 threshold
        )

        # MEDIUM issues should be upgraded to HIGH when overall_score < 50
        upgraded = [i for i in issues if i.severity in [IssueSeverity.HIGH, IssueSeverity.CRITICAL]]
        assert len(upgraded) > 0

    @pytest.mark.asyncio
    async def test_quality_trends_invalid_env_var(self):
        """Test get_quality_trends with invalid env var (lines 980-981)"""
        service = QualityService()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        db = AsyncMock()
        db.execute.return_value = mock_result

        with patch("os.getenv", return_value="invalid"):
            result = await service.get_quality_trends(db, task_id="test-task")

            assert isinstance(result, QualityTrendsResponse)
            assert result.trend_direction == "insufficient_data"

    @pytest.mark.asyncio
    async def test_trend_direction_insufficient_data(self):
        """Test get_quality_trends with insufficient data (line 1018-1019)"""
        service = QualityService()

        mock_snapshot = MagicMock()
        mock_snapshot.created_at = datetime.now(UTC)
        mock_snapshot.overall_score = 75.0
        mock_snapshot.grade = "B"
        mock_snapshot.mode = "completeness"

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_snapshot]

        db = AsyncMock()
        db.execute.return_value = mock_result

        with patch("os.getenv", return_value="10"):
            result = await service.get_quality_trends(db, task_id="test-task")

            assert result.trend_direction == "insufficient_data"
            assert result.warning is None

    @pytest.mark.asyncio
    async def test_trend_direction_calculations(self):
        """Test get_quality_trends trend direction logic (lines 1027-1040)"""
        service = QualityService()

        snapshots = []
        for i in range(5):
            snap = MagicMock()
            snap.created_at = datetime.now(UTC) + timedelta(hours=i)
            snap.overall_score = 80.0 - (i * 5)
            snap.grade = "A"
            snap.mode = "completeness"
            snapshots.append(snap)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = snapshots

        db = AsyncMock()
        db.execute.return_value = mock_result

        with patch("os.getenv", return_value="10"):
            result = await service.get_quality_trends(db, task_id="test-task")

            assert result.trend_direction in ["up", "down", "stable"]
            assert result.points_count == 5


# ---------------------------------------------------------------------------
# KeywordService
# ---------------------------------------------------------------------------
class TestKeywordServiceCoverage:
    """Tests for keyword_service.py extract/recommend methods"""

    def test_extract_from_text_basic(self):
        """extract_from_text 기본 동작"""
        service = KeywordService()
        result = service.extract_from_text(
            "프로젝트 일정 관리 회의 프로젝트 진행 상황",
            language="ko",
            max_keywords=10,
            min_score=0.0,
        )
        assert isinstance(result, KeywordResponse)
        assert result.source == "text"
        assert result.language == "ko"
        assert result.total_count > 0

    def test_extract_from_text_respects_max_keywords(self):
        """max_keywords 제한 준수"""
        service = KeywordService()
        result = service.extract_from_text(
            "프로젝트 일정 관리 회의 진행 상황 결과 분석",
            max_keywords=3,
            min_score=0.0,
        )
        assert len(result.keywords) <= 3

    def test_extract_from_text_respects_min_score(self):
        """min_score 필터링"""
        service = KeywordService()
        result = service.extract_from_text(
            "짧은 텍스트 테스트",
            max_keywords=10,
            min_score=0.9,
        )
        for item in result.keywords:
            assert item.score >= 0.9

    def test_extract_from_text_empty_result(self):
        """빈 텍스트 처리"""
        service = KeywordService()
        result = service.extract_from_text("   ", min_score=0.0)
        assert result.total_count == 0


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
class TestStatisticsCoverage:
    """Tests for statistics.py uncovered lines (lines 146, 150-151)"""

    def test_aggregate_with_invalid_timestamps(self):
        """Test _aggregate with invalid timestamps (lines 150-151)"""
        service = StatisticsService()

        segments = [
            {"speaker": "A", "start": "invalid", "end": 10.0},  # ValueError -> continue
            {"speaker": "B", "start": 0.0, "end": "bad"},  # ValueError -> continue
            {"speaker": "C", "start": 0.0, "end": 10.0, "text": "valid segment"},
        ]

        result = service._aggregate(
            task_id="test-task",
            segments=segments,
            top_n=10,
            min_len=2,
        )

        # Only the valid segment should be processed
        assert result.total_segments >= 1
        if result.speakers:
            assert any(speaker.speaker == "C" for speaker in result.speakers)
