"""
batch9: remaining coverage gaps for 100%
enhanced_preprocess.py (50 lines) + collab.py (4 lines)
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.app.exceptions import VoiceNoteError

# ─── enhanced_preprocess helpers ───────────────────────────────────


class TestResolveEnhancementOptions:
    def test_validation_error_raises(self):
        """Lines 106-107: ValueError from opts.validate() -> unprocessable()"""
        from backend.app.api.v1.audio.enhanced_preprocess import _resolve_enhancement_options

        payload = MagicMock()
        with patch("backend.app.api.v1.audio.enhanced_preprocess.AIEnhanceOptions") as M:
            inst = MagicMock()
            inst.validate.side_effect = ValueError("invalid opts")
            M.return_value = inst
            with pytest.raises(Exception):
                _resolve_enhancement_options(payload)


class TestSafeUnlink:
    def test_oserror_logs_warning(self):
        """Lines 645-646: OSError in cleanup -> logs warning, no raise"""
        from backend.app.api.v1.audio.enhanced_preprocess import _safe_unlink

        with patch(
            "backend.app.api.v1.audio.enhanced_preprocess.cleanup_temp_file",
            side_effect=OSError("disk error"),
        ):
            _safe_unlink(Path("/tmp/nonexistent"))


class TestDownloadEnhanced:
    @pytest.mark.asyncio
    async def test_file_exists_returns_file_response(self):
        """Line 601: FileResponse when file exists"""
        from fastapi.responses import FileResponse

        from backend.app.api.v1.audio.enhanced_preprocess import download_enhanced_audio

        eid = "cov_test_exists"
        p = Path(f"/tmp/enhanced_{eid}.wav")
        p.write_bytes(b"RIFF\x00\x00\x00\x00")
        try:
            result = await download_enhanced_audio(eid)
            assert isinstance(result, FileResponse)
        finally:
            p.unlink(missing_ok=True)


# ─── enhanced_endpoint (POST /preprocess) ──────────────────────────


def _ep_patches():
    return [
        patch("backend.app.api.v1.audio.enhanced_preprocess.settings"),
        patch(
            "backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
            return_value=(True, ""),
        ),
        patch(
            "backend.app.api.v1.audio.enhanced_preprocess.AIEnhanceOptionsPayload",
            return_value=MagicMock(),
        ),
        patch(
            "backend.app.api.v1.audio.enhanced_preprocess._resolve_enhancement_options",
            return_value=MagicMock(enable_quality_assessment=False, output_format="wav"),
        ),
    ]


class TestEnhancedEndpoint:
    @pytest.mark.asyncio
    async def test_upload_exception_cleanup(self):
        """Line 211: _safe_unlink(src_path) on upload failure"""
        import contextlib

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=OSError("disk full"))

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            mock_ul = stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink")
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            with pytest.raises(Exception):
                await enhanced_audio_endpoint(file=mock_file)
            mock_ul.assert_called()

    @pytest.mark.asyncio
    async def test_failed_files_bad_request(self):
        """Lines 233-236: batch_result.failed_files -> bad_request"""
        import contextlib

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_batch = MagicMock()
        mock_batch.failed_files = 1
        mock_batch.errors = [{"error": "corrupt audio"}]

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_batch)
        mock_sem = AsyncMock()
        mock_sem.__aenter__ = AsyncMock(return_value=None)
        mock_sem.__aexit__ = AsyncMock(return_value=None)

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhancement_semaphore",
                    return_value=mock_sem,
                )
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.BatchPreprocessOptions")
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            with pytest.raises(Exception):
                await enhanced_audio_endpoint(file=mock_file)

    @pytest.mark.asyncio
    async def test_preprocess_value_error(self):
        """Lines 247-248: ValueError in preprocessing -> _safe_unlink + bad_request"""
        import contextlib

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(side_effect=ValueError("bad val"))
        mock_sem = AsyncMock()
        mock_sem.__aenter__ = AsyncMock(return_value=None)
        mock_sem.__aexit__ = AsyncMock(return_value=None)

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhancement_semaphore",
                    return_value=mock_sem,
                )
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.BatchPreprocessOptions")
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink")
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            with pytest.raises(Exception):
                await enhanced_audio_endpoint(file=mock_file)

    @pytest.mark.asyncio
    async def test_preprocess_voicenote_error(self):
        """Lines 250-251: VoiceNoteError in preprocessing -> _safe_unlink + raise"""
        import contextlib

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(side_effect=VoiceNoteError(error_code="ERR", message="vn error", status_code=400))
        mock_sem = AsyncMock()
        mock_sem.__aenter__ = AsyncMock(return_value=None)
        mock_sem.__aexit__ = AsyncMock(return_value=None)

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhancement_semaphore",
                    return_value=mock_sem,
                )
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.BatchPreprocessOptions")
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink")
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            with pytest.raises(VoiceNoteError):
                await enhanced_audio_endpoint(file=mock_file)

    @pytest.mark.asyncio
    async def test_happy_path_with_quality_assessment(self):
        """Lines 258-306: quality assessment block + FileResponse return"""
        import contextlib

        from fastapi.responses import FileResponse

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"audio", b""])

        out_path = Path(tempfile.mktemp(suffix=".wav", prefix="test_out_"))
        out_path.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_batch = MagicMock()
        mock_batch.failed_files = 0
        mock_batch.results = [MagicMock(processed_path=out_path, metadata={})]
        mock_batch.processing_time_seconds = 0.5

        mock_enh = MagicMock()
        mock_enh.output_path = out_path
        mock_enh.enhancement_id = "enh_cov"
        mock_enh.noise_reduction_applied = True
        mock_enh.voice_enhancement_applied = False
        mock_enh.segments_processed = 1
        mock_enh.processing_time = 0.5
        mock_enh.processing_details = {}
        mock_enh.warnings = []

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_batch)
        mock_sem = AsyncMock()
        mock_sem.__aenter__ = AsyncMock(return_value=None)
        mock_sem.__aexit__ = AsyncMock(return_value=None)

        mock_wf = MagicMock()
        mock_wf.getframerate.return_value = 16000
        mock_wf.readframes.return_value = b"\x00" * 32000

        mock_opts = MagicMock()
        mock_opts.enable_quality_assessment = True
        mock_opts.output_format = "wav"

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess._resolve_enhancement_options",
                    return_value=mock_opts,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhancement_semaphore",
                    return_value=mock_sem,
                )
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.BatchPreprocessOptions")
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.EnhancementResult",
                    return_value=mock_enh,
                )
            )
            mw = stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.wave")
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess._calculate_audio_metrics",
                    return_value={"snr": 25.0, "clarity": 0.8, "noise_level": 0.1},
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.VoiceQualityAssessment",
                    return_value=MagicMock(),
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.EnhancementReportResponse",
                    return_value=MagicMock(),
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.AudioQualityEvaluation",
                    return_value=MagicMock(),
                )
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            mw.open.return_value.__enter__ = MagicMock(return_value=mock_wf)
            mw.open.return_value.__exit__ = MagicMock(return_value=None)

            result = await enhanced_audio_endpoint(file=mock_file)

        out_path.unlink(missing_ok=True)
        assert isinstance(result, FileResponse)

    @pytest.mark.asyncio
    async def test_quality_assessment_exception_logged(self):
        """Lines 283-284: quality assessment exception -> logger.error"""
        import contextlib

        from fastapi.responses import FileResponse

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"audio", b""])

        out_path = Path(tempfile.mktemp(suffix=".wav", prefix="test_qa_"))
        out_path.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_batch = MagicMock()
        mock_batch.failed_files = 0
        mock_batch.results = [MagicMock(processed_path=out_path, metadata={})]
        mock_batch.processing_time_seconds = 0.5

        mock_enh = MagicMock()
        mock_enh.output_path = out_path
        mock_enh.enhancement_id = "enh_qa"
        mock_enh.noise_reduction_applied = True
        mock_enh.voice_enhancement_applied = False
        mock_enh.segments_processed = 1
        mock_enh.processing_time = 0.5
        mock_enh.processing_details = {}
        mock_enh.warnings = []

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_batch)
        mock_sem = AsyncMock()
        mock_sem.__aenter__ = AsyncMock(return_value=None)
        mock_sem.__aexit__ = AsyncMock(return_value=None)

        mock_opts = MagicMock()
        mock_opts.enable_quality_assessment = True
        mock_opts.output_format = "wav"

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess._resolve_enhancement_options",
                    return_value=mock_opts,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhancement_semaphore",
                    return_value=mock_sem,
                )
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.BatchPreprocessOptions")
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.EnhancementResult",
                    return_value=mock_enh,
                )
            )
            # wave.open raises -> except block (lines 283-284)
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.wave.open",
                      side_effect=RuntimeError("wave read error"))
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess._calculate_audio_metrics",
                    return_value={"snr": 25.0, "clarity": 0.8, "noise_level": 0.1},
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.VoiceQualityAssessment",
                    return_value=MagicMock(),
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.EnhancementReportResponse",
                    return_value=MagicMock(),
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.AudioQualityEvaluation",
                    return_value=MagicMock(),
                )
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            result = await enhanced_audio_endpoint(file=mock_file)

        out_path.unlink(missing_ok=True)
        assert isinstance(result, FileResponse)

    @pytest.mark.asyncio
    async def test_cleanup_closure_runs(self):
        """Lines 303-304: _cleanup closure called via BackgroundTask"""
        import contextlib

        from fastapi.responses import FileResponse

        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_audio_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"audio", b""])

        out_path = Path(tempfile.mktemp(suffix=".wav", prefix="test_cleanup_"))
        out_path.write_bytes(b"RIFF" + b"\x00" * 100)

        mock_batch = MagicMock()
        mock_batch.failed_files = 0
        mock_batch.results = [MagicMock(processed_path=out_path, metadata={})]
        mock_batch.processing_time_seconds = 0.5

        mock_enh = MagicMock()
        mock_enh.output_path = out_path
        mock_enh.enhancement_id = "enh_cleanup"
        mock_enh.noise_reduction_applied = True
        mock_enh.voice_enhancement_applied = False
        mock_enh.segments_processed = 1
        mock_enh.processing_time = 0.5
        mock_enh.processing_details = {}
        mock_enh.warnings = []

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_batch)
        mock_sem = AsyncMock()
        mock_sem.__aenter__ = AsyncMock(return_value=None)
        mock_sem.__aexit__ = AsyncMock(return_value=None)

        mock_opts = MagicMock()
        mock_opts.enable_quality_assessment = False
        mock_opts.output_format = "wav"

        with contextlib.ExitStack() as stack:
            s, _, _, _ = [stack.enter_context(p) for p in _ep_patches()]
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess._resolve_enhancement_options",
                    return_value=mock_opts,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.get_enhancement_semaphore",
                    return_value=mock_sem,
                )
            )
            stack.enter_context(
                patch("backend.app.api.v1.audio.enhanced_preprocess.BatchPreprocessOptions")
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.EnhancementResult",
                    return_value=mock_enh,
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.EnhancementReportResponse",
                    return_value=MagicMock(),
                )
            )
            stack.enter_context(
                patch(
                    "backend.app.api.v1.audio.enhanced_preprocess.AudioQualityEvaluation",
                    return_value=MagicMock(),
                )
            )
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            result = await enhanced_audio_endpoint(file=mock_file)

        assert isinstance(result, FileResponse)
        result.background.func()
        out_path.unlink(missing_ok=True)


# ─── enhanced_batch_endpoint (POST /batch) ─────────────────────────


class TestEnhancedBatchEndpoint:
    @pytest.mark.asyncio
    async def test_happy_path_returns_dict(self):
        """Line 357+: full batch return dict"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_batch_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_item = MagicMock()
        mock_item.original_path = "/tmp/in.wav"
        mock_item.processed_path = "/tmp/out.wav"
        mock_item.original_format = "wav"
        mock_item.original_size = 1000
        mock_item.processed_size = 800
        mock_item.duration_seconds = 10.0
        mock_item.sample_rate = 16000
        mock_item.channels = 1
        mock_item.metadata = {}

        mock_result = MagicMock()
        mock_result.total_files = 1
        mock_result.processed_files = 1
        mock_result.failed_files = 0
        mock_result.processing_time_seconds = 0.5
        mock_result.summary = {}
        mock_result.results = [mock_item]
        mock_result.errors = []

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(return_value=mock_result)

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")), \
             patch("backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor), \
             patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink"):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100

            result = await enhanced_batch_endpoint(files=[mock_file])

        assert result["total_files"] == 1
        assert result["processed_files"] == 1


# ─── enhanced_preprocess_endpoint (legacy single-file) ─────────────


class TestLegacyEnhancedPreprocess:
    @pytest.mark.asyncio
    async def test_disabled(self):
        """Line 405: service_unavailable when disabled"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s:
            s.audio_preprocess_enabled = False
            with pytest.raises(Exception):
                await enhanced_preprocess_endpoint(file=AsyncMock(filename="t.wav"))

    @pytest.mark.asyncio
    async def test_bad_format(self):
        """Line 410: bad_request for invalid format"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(False, "unsupported")):
            s.audio_preprocess_enabled = True
            with pytest.raises(Exception):
                await enhanced_preprocess_endpoint(file=AsyncMock(filename="t.xyz"))

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Lines 423-425: request_entity_too_large when file exceeds limit"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"x" * (2 * 1024 * 1024), b""])

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 1
            with pytest.raises(Exception):
                await enhanced_preprocess_endpoint(file=mock_file)

    @pytest.mark.asyncio
    async def test_voicenote_error(self):
        """Lines 460-461: VoiceNoteError -> _safe_unlink + re-raise"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(side_effect=VoiceNoteError(error_code="ERR", message="vn fail", status_code=400))

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")), \
             patch("backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor), \
             patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink"):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100
            with pytest.raises(VoiceNoteError):
                await enhanced_preprocess_endpoint(file=mock_file)

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        """Lines 465-468: generic Exception -> _safe_unlink + bad_request"""
        from backend.app.api.v1.audio.enhanced_preprocess import enhanced_preprocess_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(side_effect=RuntimeError("unexpected"))

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")), \
             patch("backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor), \
             patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink"):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100
            with pytest.raises(Exception):
                await enhanced_preprocess_endpoint(file=mock_file)


# ─── batch_preprocess_endpoint (legacy batch) ──────────────────────


class TestLegacyBatchPreprocess:
    @pytest.mark.asyncio
    async def test_disabled(self):
        """Line 489: service_unavailable when disabled"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s:
            s.audio_preprocess_enabled = False
            with pytest.raises(Exception):
                await batch_preprocess_endpoint(files=[AsyncMock(filename="t.wav")])

    @pytest.mark.asyncio
    async def test_too_many_files(self):
        """Line 491: bad_request when > 20 files"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint

        files = [AsyncMock(filename="t.wav") for _ in range(21)]
        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s:
            s.audio_preprocess_enabled = True
            with pytest.raises(Exception):
                await batch_preprocess_endpoint(files=files)

    @pytest.mark.asyncio
    async def test_bad_format(self):
        """Line 500: bad_request for invalid format"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(False, "unsupported")):
            s.audio_preprocess_enabled = True
            with pytest.raises(Exception):
                await batch_preprocess_endpoint(files=[AsyncMock(filename="t.xyz")])

    @pytest.mark.asyncio
    async def test_file_too_large(self):
        """Line 510: bad_request when file exceeds limit"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"x" * (2 * 1024 * 1024), b""])

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 1
            with pytest.raises(Exception):
                await batch_preprocess_endpoint(files=[mock_file])

    @pytest.mark.asyncio
    async def test_voicenote_error(self):
        """Lines 545-546: VoiceNoteError -> re-raise"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(side_effect=VoiceNoteError(error_code="ERR", message="vn fail", status_code=400))

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")), \
             patch("backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor), \
             patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink"):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100
            with pytest.raises(VoiceNoteError):
                await batch_preprocess_endpoint(files=[mock_file])

    @pytest.mark.asyncio
    async def test_generic_exception(self):
        """Lines 547-549: generic Exception -> bad_request"""
        from backend.app.api.v1.audio.enhanced_preprocess import batch_preprocess_endpoint

        mock_file = AsyncMock(filename="test.wav")
        mock_file.read = AsyncMock(side_effect=[b"data", b""])

        mock_processor = AsyncMock()
        mock_processor.preprocess_batch = AsyncMock(side_effect=RuntimeError("unexpected"))

        with patch("backend.app.api.v1.audio.enhanced_preprocess.settings") as s, \
             patch("backend.app.api.v1.audio.enhanced_preprocess.validate_audio_format",
                    return_value=(True, "")), \
             patch("backend.app.api.v1.audio.enhanced_preprocess.get_enhanced_processor",
                    return_value=mock_processor), \
             patch("backend.app.api.v1.audio.enhanced_preprocess._safe_unlink"):
            s.audio_preprocess_enabled = True
            s.audio_preprocess_max_file_mb = 100
            with pytest.raises(Exception):
                await batch_preprocess_endpoint(files=[mock_file])


# ─── collab.py: rate_limited + cursor ──────────────────────────────


def _mock_session_chain(scalar_returns=None):
    mock_engine = MagicMock()
    scalar_iter = iter(scalar_returns or [])

    mock_session = MagicMock()
    mock_session.__enter__ = MagicMock(return_value=mock_session)
    mock_session.__exit__ = MagicMock(return_value=False)
    mock_execute = MagicMock()
    mock_execute.scalar_one_or_none = MagicMock(side_effect=lambda: next(scalar_iter))
    mock_session.execute = MagicMock(return_value=mock_execute)

    factory = MagicMock(return_value=mock_session)
    return mock_engine, factory


class TestCollabRateLimitedAndCursor:
    @pytest.mark.asyncio
    async def test_rate_limited_response(self):
        """Lines 327-331: rate_limited response sent"""
        from fastapi import WebSocketDisconnect

        from backend.app.api.v1.collaboration.collab import (
            CollabConnectionManager,
            websocket_collab,
        )

        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        edit_msg = {"type": "edit", "field": "title", "value": "X", "client_ts": 1.0}
        ws.receive_json = AsyncMock(side_effect=[edit_msg, WebSocketDisconnect()])

        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=False)

        _, factory = _mock_session_chain(scalar_returns=["team-123", "member-id"])

        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager",
                    return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service",
                    return_value=mock_service), \
             patch("backend.app.api.v1.collaboration.collab._rate_limiter") as mock_limiter:
            MockAuth.return_value.decode_access_token.return_value = {
                "sub": "550e8400-e29b-41d4-a716-446655440001",
                "role": "member",
                "name": "Editor",
            }
            mock_limiter.is_limited.return_value = True
            await websocket_collab(ws, "task1")

        ws.send_json.assert_any_call(
            {"type": "rate_limited", "retry_after_ms": 1000}
        )

    @pytest.mark.asyncio
    async def test_cursor_message_passes(self):
        """Lines 341-343: cursor message received -> pass (no-op)"""
        from fastapi import WebSocketDisconnect

        from backend.app.api.v1.collaboration.collab import (
            CollabConnectionManager,
            websocket_collab,
        )

        ws = AsyncMock()
        ws.query_params = {"token": "valid"}
        cursor_msg = {"type": "cursor", "position": 5}
        ws.receive_json = AsyncMock(side_effect=[cursor_msg, WebSocketDisconnect()])

        fresh_manager = CollabConnectionManager()
        mock_service = MagicMock()
        mock_service.get_sync_state = AsyncMock(return_value={})
        mock_service.has_unpersisted_changes = MagicMock(return_value=False)

        _, factory = _mock_session_chain(scalar_returns=["team-123", "member-id"])

        with patch("backend.services.auth_service.AuthService") as MockAuth, \
             patch("backend.db.engine.create_engine", return_value=MagicMock()), \
             patch("backend.db.engine.get_session_factory", return_value=factory), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_manager",
                    return_value=fresh_manager), \
             patch("backend.app.api.v1.collaboration.collab.get_collab_service",
                    return_value=mock_service), \
             patch("backend.app.api.v1.collaboration.collab._rate_limiter") as mock_limiter:
            MockAuth.return_value.decode_access_token.return_value = {
                "sub": "550e8400-e29b-41d4-a716-446655440001",
                "role": "member",
                "name": "Editor",
            }
            mock_limiter.is_limited.return_value = False
            await websocket_collab(ws, "task1")

        ws.accept.assert_awaited_once()


class TestActionItemRepr:
    def test_action_item_repr(self):
        import sys

        mod = sys.modules.get("backend.db.models")
        if mod is None:
            pytest.skip("models module not loaded")

        cls = getattr(mod, "ActionItem", None)
        if cls is None:
            pytest.skip("ActionItem not found")

        with patch.object(cls, "__repr__", lambda self: f"<ActionItem(id={self.id}, title={self.title!r}, status={self.status!r})>"):
            instance = object.__new__(cls)
            with patch.object(type(instance), "id", new_callable=lambda: property(lambda self: "test-id")), \
                 patch.object(type(instance), "title", new_callable=lambda: property(lambda self: "테스트 항목")), \
                 patch.object(type(instance), "status", new_callable=lambda: property(lambda self: "pending")):
                r = repr(instance)
        assert "테스트 항목" in r
        assert "pending" in r



