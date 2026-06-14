"""
quality_assessment.py + enhanced_preprocess.py → 100% 커버리지
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===========================================================================
# quality_assessment.py (97% → 100%)
# 미커버 라인: 174, 291, 324, 348, 383
# ===========================================================================


class TestQualityAssessmentFull:
    @pytest.mark.asyncio
    async def test_request_assessment_no_minutes_content(self):
        """line 174: request_quality_assessment에서 회의록 내용이 없을 때 not_found"""
        from backend.app.api.v1.audio.quality_assessment import request_quality_assessment
        from backend.app.exceptions import NotFoundError

        mock_db = AsyncMock()
        mock_task = MagicMock()
        mock_task.result_data = {}  # 빈 데이터 → _extract_minutes_text returns ""
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = mock_task
        mock_db.execute = AsyncMock(return_value=mock_scalar)

        mock_svc = AsyncMock()
        mock_payload = MagicMock()

        with pytest.raises(NotFoundError):
            await request_quality_assessment(
                task_id="test-task",
                payload=mock_payload,
                db=mock_db,
                svc=mock_svc,
            )

    @pytest.mark.asyncio
    async def test_live_score_voice_note_error_reraise(self):
        """line 291: compute_live_score VoiceNoteError re-raise"""
        from backend.app.api.v1.audio.quality_assessment import get_live_quality_score
        from backend.app.exceptions import VoiceNoteError

        vne = VoiceNoteError(error_code="LIVE_ERR", message="라이브 점수 오류", status_code=500)
        mock_svc = AsyncMock()
        mock_svc.compute_live_score = AsyncMock(side_effect=vne)

        with patch(
            "backend.app.api.v1.audio.quality_assessment._load_minutes_text_or_404",
            new=AsyncMock(return_value="회의 내용"),
        ):
            with pytest.raises(VoiceNoteError):
                await get_live_quality_score(
                    task_id="test-task",
                    persist=True,
                    db=AsyncMock(),
                    svc=mock_svc,
                )

    @pytest.mark.asyncio
    async def test_submit_feedback_voice_note_error_reraise(self):
        """line 324: submit_feedback VoiceNoteError re-raise"""
        from backend.app.api.v1.audio.quality_assessment import submit_quality_feedback
        from backend.app.exceptions import VoiceNoteError

        vne = VoiceNoteError(error_code="FB_ERR", message="피드백 오류", status_code=500)
        mock_db = AsyncMock()
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = MagicMock()
        mock_db.execute = AsyncMock(return_value=mock_scalar)

        mock_svc = AsyncMock()
        mock_svc.submit_feedback = AsyncMock(side_effect=vne)

        with pytest.raises(VoiceNoteError):
            await submit_quality_feedback(
                task_id="test-task",
                payload=MagicMock(),
                db=mock_db,
                svc=mock_svc,
            )

    @pytest.mark.asyncio
    async def test_list_feedback_voice_note_error_reraise(self):
        """line 348: get_feedback_summary VoiceNoteError re-raise"""
        from backend.app.api.v1.audio.quality_assessment import list_quality_feedback
        from backend.app.exceptions import VoiceNoteError

        vne = VoiceNoteError(error_code="LIST_ERR", message="목록 오류", status_code=500)
        mock_svc = AsyncMock()
        mock_svc.get_feedback_summary = AsyncMock(side_effect=vne)

        with pytest.raises(VoiceNoteError):
            await list_quality_feedback(
                task_id="test-task",
                recent_limit=10,
                db=AsyncMock(),
                svc=mock_svc,
            )

    @pytest.mark.asyncio
    async def test_quality_trends_voice_note_error_reraise(self):
        """line 383: get_quality_trends VoiceNoteError re-raise"""
        from backend.app.api.v1.audio.quality_assessment import get_quality_trends
        from backend.app.exceptions import VoiceNoteError

        vne = VoiceNoteError(error_code="TREND_ERR", message="추세 오류", status_code=500)
        mock_svc = AsyncMock()
        mock_svc.get_quality_trends = AsyncMock(side_effect=vne)

        with pytest.raises(VoiceNoteError):
            await get_quality_trends(
                task_id="test-task",
                limit=50,
                warning_drop_threshold=None,
                db=AsyncMock(),
                svc=mock_svc,
            )


# ===========================================================================
# enhanced_preprocess.py (89% → 100%)
# 미커버 라인: 134-161 (성공 경로), 278-280 (보고서 생성)
# ===========================================================================

# BatchSummary에 필요한 필드를 모두 포함한 summary dict
_FULL_SUMMARY = {
    "total_input_size_bytes": 2000,
    "total_output_size_bytes": 1600,
    "compression_ratio": 0.8,
    "total_duration_seconds": 20.0,
    "average_duration_seconds": 10.0,
    "average_sample_rate": 44100,
    "format_distribution": {"wav": 1},
}


class TestEnhancedPreprocessFull:
    @pytest.mark.asyncio
    async def test_single_preprocess_success(self):
        """lines 134-167: 전처리 성공 → StreamingResponse 반환 + cleanup(lines 157-158) 실행"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint
        from backend.pipeline.enhanced_audio_processor import BatchPreprocessResult

        processed = MagicMock()
        processed.original_size = 1000
        processed.processed_size = 800
        processed.duration_seconds = 10.0
        processed.sample_rate = 44100
        processed.channels = 1
        processed.processed_path = Path("/tmp/test_processed.wav")
        processed.metadata = {"ai_noise_removed": True}

        mock_result = BatchPreprocessResult(
            task_id="single-ok",
            total_files=1,
            processed_files=1,
            failed_files=0,
            processing_time_seconds=0.5,
            results=[processed],
            errors=[],
            summary={},
        )

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_result)

        mock_file = MagicMock()
        mock_file.filename = "test.wav"
        mock_file.read = AsyncMock(side_effect=[b"RIFF" + b"\x00" * 100, b""])

        # FileResponse background task를 캡처하여 cleanup 함수 실행
        mock_response = MagicMock()
        mock_response.media_type = "audio/wav"

        captured_calls = {}

        def capture_file_response(*args, **kwargs):
            # background task 캡처하여 cleanup 함수 실행
            bg_task = kwargs.get("background")
            if bg_task and hasattr(bg_task, "func"):
                captured_calls["cleanup"] = bg_task.func
            return mock_response

        with (
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                return_value=mock_processor,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.settings",
                audio_preprocess_enabled=True,
                audio_preprocess_max_file_mb=100,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.FileResponse",
                side_effect=capture_file_response,
            ),
            patch.object(Path, "unlink"),
        ):
            resp = await enhanced_preprocess_endpoint(
                file=mock_file,
                convert_to_16k_mono=True,
                normalize=True,
                target_dbfs=-20.0,
                high_pass_hz=None,
                low_pass_hz=None,
                trim_silence=False,
                silence_threshold_db=-40.0,
                silence_min_len_ms=700,
                ai_noise_removal=True,
                noise_threshold=0.1,
                denoise_strength=0.8,
            )
            assert resp is not None

            # cleanup 함수 실행하여 lines 157-158 커버
            if "cleanup" in captured_calls:
                captured_calls["cleanup"]()

    @pytest.mark.asyncio
    async def test_single_preprocess_failed_400(self):
        """lines 134-138: failed_files > 0 → HTTPException(400)"""
        from fastapi import HTTPException

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint
        from backend.pipeline.enhanced_audio_processor import BatchPreprocessResult

        mock_result = BatchPreprocessResult(
            task_id="single-fail",
            total_files=1,
            processed_files=0,
            failed_files=1,
            processing_time_seconds=0.1,
            results=[],
            errors=[{"file": "bad.wav", "error": "실패"}],
            summary={},
        )

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_result)

        mock_file = MagicMock()
        mock_file.filename = "bad.wav"
        mock_file.read = AsyncMock(side_effect=[b"RIFF" + b"\x00" * 10, b""])

        with (
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                return_value=mock_processor,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.settings",
                audio_preprocess_enabled=True,
                audio_preprocess_max_file_mb=100,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await enhanced_preprocess_endpoint(
                    file=mock_file,
                    convert_to_16k_mono=True,
                    normalize=True,
                    target_dbfs=-20.0,
                    high_pass_hz=None,
                    low_pass_hz=None,
                    trim_silence=False,
                    silence_threshold_db=-40.0,
                    silence_min_len_ms=700,
                    ai_noise_removal=True,
                    noise_threshold=0.1,
                    denoise_strength=0.8,
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_batch_with_report(self):
        """lines 278-280: return_report=True → create_processing_report"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint
        from backend.pipeline.enhanced_audio_processor import BatchPreprocessResult

        mock_result = BatchPreprocessResult(
            task_id="batch-ok",
            total_files=1,
            processed_files=1,
            failed_files=0,
            processing_time_seconds=1.0,
            results=[],
            errors=[],
            summary=_FULL_SUMMARY,
        )

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_result)
        mock_processor.create_processing_report = AsyncMock(return_value='{"task_id": "batch-ok"}')

        mock_file = MagicMock()
        mock_file.filename = "test.wav"
        mock_file.read = AsyncMock(side_effect=[b"RIFF" + b"\x00" * 10, b""])

        with (
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                return_value=mock_processor,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.settings",
                audio_preprocess_enabled=True,
                audio_preprocess_max_file_mb=100,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            resp = await batch_preprocess_endpoint(
                files=[mock_file],
                convert_to_16k_mono=True,
                normalize=True,
                target_dbfs=-20.0,
                high_pass_hz=None,
                low_pass_hz=None,
                trim_silence=False,
                silence_threshold_db=-40.0,
                silence_min_len_ms=700,
                ai_noise_removal=True,
                noise_threshold=0.1,
                denoise_strength=0.8,
                output_format="zip",
                return_report=True,
            )
            mock_processor.create_processing_report.assert_called_once_with(mock_result)
            assert resp.report is not None

    @pytest.mark.asyncio
    async def test_batch_without_report(self):
        """line 278: return_report=False → report=None"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint
        from backend.pipeline.enhanced_audio_processor import BatchPreprocessResult

        mock_result = BatchPreprocessResult(
            task_id="batch-nr",
            total_files=1,
            processed_files=1,
            failed_files=0,
            processing_time_seconds=1.0,
            results=[],
            errors=[],
            summary=_FULL_SUMMARY,
        )

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_result)

        mock_file = MagicMock()
        mock_file.filename = "test.wav"
        mock_file.read = AsyncMock(side_effect=[b"RIFF" + b"\x00" * 10, b""])

        with (
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                return_value=mock_processor,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.settings",
                audio_preprocess_enabled=True,
                audio_preprocess_max_file_mb=100,
            ),
            patch(
                "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                return_value=(True, ""),
            ),
        ):
            resp = await batch_preprocess_endpoint(
                files=[mock_file],
                convert_to_16k_mono=True,
                normalize=True,
                target_dbfs=-20.0,
                high_pass_hz=None,
                low_pass_hz=None,
                trim_silence=False,
                silence_threshold_db=-40.0,
                silence_min_len_ms=700,
                ai_noise_removal=True,
                noise_threshold=0.1,
                denoise_strength=0.8,
                output_format="zip",
                return_report=False,
            )
            mock_processor.create_processing_report.assert_not_called()
            assert resp.report is None
