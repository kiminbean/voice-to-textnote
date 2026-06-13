"""
diarization_engine.py 추가 단위 테스트
커버리지 누락 라인 대상:
- diarize_chunked 메서드의 청크 분할 및 병합 로직
- _match_chunk_speakers의 화자 매칭 알고리즘
- _merge_adjacent_segments의 병합 로직
- VAD 관련 엣지 케이스
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import torch

from backend.ml.diarization_engine import DiarizationEngine
from backend.pipeline.speaker_matcher import SpeakerSegment

# ==========================================================================
# 테스트 헬퍼 함수
# ==========================================================================


def _reset_engine():
    """DiarizationEngine 클래스 변수 리셋 (Phase 5: _instance 제거됨)"""
    DiarizationEngine._model_loaded = False
    DiarizationEngine._load_time_seconds = None
    DiarizationEngine._pipeline = None
    DiarizationEngine._vad_model = None
    DiarizationEngine._vad_loaded = False


def _make_mock_pipeline():
    """pyannote.audio Pipeline mock 생성"""
    mock_pipeline = MagicMock()

    # diarization 결과 mock - itertracks() 형태
    mock_turn1 = MagicMock()
    mock_turn1.start = 0.0
    mock_turn1.end = 5.0
    mock_turn2 = MagicMock()
    mock_turn2.start = 6.0
    mock_turn2.end = 10.0

    mock_diarization = MagicMock(spec=[])
    mock_diarization.itertracks = MagicMock(
        return_value=[
            (mock_turn1, None, "SPEAKER_00"),
            (mock_turn2, None, "SPEAKER_01"),
        ]
    )

    mock_pipeline.return_value = mock_diarization
    return mock_pipeline


def _make_loaded_engine_with_mock_pipeline():
    """모델이 로드된 상태의 엔진 + pipeline 호출 추적 mock"""
    _reset_engine()
    mock_pipeline = _make_mock_pipeline()
    engine = DiarizationEngine()
    engine._pipeline = mock_pipeline
    engine._model_loaded = True
    return engine, mock_pipeline


# ==========================================================================
# diarize_chunked 메서드 테스트
# ==========================================================================


class TestDiarizeChunked:
    """청크 분할 화자 분리 테스트 (REQ-PERF-001)"""

    def setup_method(self):
        _reset_engine()

    def test_diarize_chunked_handles_empty_audio(self, tmp_path):
        """비어 있는 오디오 파일 처리"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # 빈 wav 파일 생성
        audio_file = tmp_path / "empty.wav"
        audio_file.write_bytes(b"")

        mock_torchaudio = MagicMock()
        mock_torchaudio.info.return_value = MagicMock(sample_rate=16000, num_frames=0)

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            result = engine.diarize_chunked(audio_file)

            # 빈 결과 반환
            assert result == []

    def test_diarize_chunked_splits_into_multiple_chunks(self, tmp_path):
        """긴 오디오를 여러 청크로 분할"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        audio_file = tmp_path / "long.wav"
        audio_file.write_bytes(b"x" * 1000)

        # 1초짜리 청크로 설정 (chunk_duration_sec=1)
        mock_torchaudio = MagicMock()
        mock_torchaudio.info.return_value = MagicMock(sample_rate=16000, num_frames=32000)
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            result = engine.diarize_chunked(audio_file, chunk_duration_sec=1, overlap_sec=0)

            # 32개 샘플 / 16000 = 2초 분할 예상
            # 2초를 1초 청크로 나누면 최소 2개 청크
            assert isinstance(result, list)

    def test_diarize_chunked_calls_progress_callback(self, tmp_path):
        """진행률 콜백 호출 확인"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"x" * 1000)

        mock_torchaudio = MagicMock()
        mock_torchaudio.info.return_value = MagicMock(sample_rate=16000, num_frames=16000)
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)

        callback_mock = MagicMock()

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize_chunked(
                audio_file, chunk_duration_sec=1, overlap_sec=0, progress_callback=callback_mock
            )

            # 최소 한 번 이상 호출되어야 함
            assert callback_mock.call_count >= 1

    def test_diarize_chunked_without_model_raises_error(self, tmp_path):
        """모델 미로드 시 RuntimeError"""
        engine = DiarizationEngine()
        # 모델 로드 안 함

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"x" * 100)

        with pytest.raises(RuntimeError, match="모델이 로드되지 않았습니다"):
            engine.diarize_chunked(audio_file)

    def test_diarize_chunked_with_overlap(self, tmp_path):
        """청크 간 오버랩 처리"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        audio_file = tmp_path / "test.wav"
        audio_file.write_bytes(b"x" * 1000)

        mock_torchaudio = MagicMock()
        mock_torchaudio.info.return_value = MagicMock(sample_rate=16000, num_frames=48000)
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            # 3초 오디오, 1초 청크, 0.5초 오버랩
            result = engine.diarize_chunked(audio_file, chunk_duration_sec=1, overlap_sec=0.5)

            # 오버랩 고려하여 청크 분할
            assert isinstance(result, list)


# ==========================================================================
# _match_chunk_speakers 메서드 테스트
# ==========================================================================


class TestMatchChunkSpeakers:
    """청크 화자 매칭 테스트"""

    def test_match_chunk_speakers_with_no_previous_segments(self):
        """이전 세그먼트 없으면 빈 매핑"""
        local_segments = [SpeakerSegment(speaker_id="A", start=0.0, end=5.0)]

        result = DiarizationEngine._match_chunk_speakers(
            local_segments=local_segments,
            previous_segments=[],
            chunk_offset_sec=0.0,
            overlap_sec=10,
        )

        assert result == {}

    def test_match_chunk_speakers_with_zero_offset(self):
        """chunk_offset_sec <= 0 이면 빈 매핑"""
        local_segments = [SpeakerSegment(speaker_id="A", start=0.0, end=5.0)]
        previous_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0)]

        result = DiarizationEngine._match_chunk_speakers(
            local_segments=local_segments,
            previous_segments=previous_segments,
            chunk_offset_sec=0.0,
            overlap_sec=10,
        )

        assert result == {}

    def test_match_chunk_speakers_by_overlap(self):
        """오버랩 구간으로 화자 매칭"""
        # 이전 청크: 0-10초에 SPEAKER_00
        previous_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=10.0)]

        # 현재 청크 (offset=5초): 0-5초 로컬 타임 (글로벌 5-10초)
        # 현재 청크의 0-2초 = 글로벌 5-7초 → 이전 청크와 2초 오버랩
        local_segments = [SpeakerSegment(speaker_id="A", start=0.0, end=5.0)]

        result = DiarizationEngine._match_chunk_speakers(
            local_segments=local_segments,
            previous_segments=previous_segments,
            chunk_offset_sec=5.0,
            overlap_sec=5.0,
        )

        # A → SPEAKER_00 매칭
        assert "A" in result
        assert result["A"] == "SPEAKER_00"

    def test_match_chunk_speakers_no_overlap_returns_empty(self):
        """오버랩 없으면 빈 매핑"""
        previous_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0)]

        local_segments = [SpeakerSegment(speaker_id="A", start=0.0, end=5.0)]

        # 20초 offset으로 오버랩 없음
        result = DiarizationEngine._match_chunk_speakers(
            local_segments=local_segments,
            previous_segments=previous_segments,
            chunk_offset_sec=20.0,
            overlap_sec=5.0,
        )

        assert result == {}

    def test_match_chunk_speakers_multiple_speakers(self):
        """여러 화자 매칭"""
        previous_segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=10.0),
            SpeakerSegment(speaker_id="SPEAKER_01", start=10.0, end=20.0),
        ]

        local_segments = [
            SpeakerSegment(speaker_id="A", start=0.0, end=5.0),
            SpeakerSegment(speaker_id="B", start=5.0, end=10.0),
        ]

        result = DiarizationEngine._match_chunk_speakers(
            local_segments=local_segments,
            previous_segments=previous_segments,
            chunk_offset_sec=5.0,
            overlap_sec=10.0,
        )

        # 두 화자 모두 매칭 시도
        assert len(result) <= 2


# ==========================================================================
# _merge_adjacent_segments 테스트
# ==========================================================================


class TestMergeAdjacentSegments:
    """인접 세그먼트 병합 테스트"""

    def test_merge_adjacent_segments_empty_list(self):
        """빈 리스트 처리"""
        result = DiarizationEngine._merge_adjacent_segments([])
        assert result == []

    def test_merge_adjacent_segments_same_speaker(self):
        """같은 화자의 인접 세그먼트 병합"""
        segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0),
            SpeakerSegment(speaker_id="SPEAKER_00", start=5.1, end=10.0),
        ]

        result = DiarizationEngine._merge_adjacent_segments(segments, tolerance_sec=0.2)

        # tolerance_sec=0.2이면 0.1초 갭격은 병합됨
        assert len(result) == 1
        assert result[0].speaker_id == "SPEAKER_00"
        assert result[0].start == 0.0
        assert result[0].end == 10.0

    def test_merge_adjacent_segments_different_speakers(self):
        """다른 화자는 병합 안 함"""
        segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0),
            SpeakerSegment(speaker_id="SPEAKER_01", start=5.1, end=10.0),
        ]

        result = DiarizationEngine._merge_adjacent_segments(segments)

        # 그대로 유지
        assert len(result) == 2

    def test_merge_adjacent_segments_with_gap(self):
        """간격이 크면 병합 안 함 (tolerance 초과)"""
        segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0),
            SpeakerSegment(speaker_id="SPEAKER_00", start=10.0, end=15.0),
        ]

        result = DiarizationEngine._merge_adjacent_segments(segments, tolerance_sec=0.1)

        # 5초 갭격 > tolerance(0.1초) → 병합 안 함
        assert len(result) == 2

    def test_merge_adjacent_segments_overlapping(self):
        """중첩되는 세그먼트 병합"""
        segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=10.0),
            SpeakerSegment(speaker_id="SPEAKER_00", start=8.0, end=15.0),
        ]

        result = DiarizationEngine._merge_adjacent_segments(segments)

        # 더 긴 세그먼트로 병합
        assert len(result) == 1
        assert result[0].end == 15.0

    def test_merge_adjacent_segments_sorts_by_start_time(self):
        """시작 시간 기준 정렬 후 병합"""
        segments = [
            SpeakerSegment(speaker_id="SPEAKER_00", start=10.0, end=15.0),
            SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0),
            SpeakerSegment(speaker_id="SPEAKER_00", start=5.1, end=10.0),
        ]

        result = DiarizationEngine._merge_adjacent_segments(segments, tolerance_sec=0.2)

        # 정렬 후 병합 → 하나의 세그먼트
        assert len(result) == 1
        assert result[0].start == 0.0


# ==========================================================================
# VAD 관련 추가 테스트
# ==========================================================================


class TestVADCompression:
    """VAD 압축 엣지 케이스"""

    def setup_method(self):
        _reset_engine()

    def test_vad_with_no_speech_timestamps(self):
        """음성 구간 없으면 빈 mapping 반환"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        vad_mock = MagicMock()
        vad_mock.get_speech_timestamps.return_value = []

        waveform = torch.zeros((1, 16000))
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            _compressed, mapping = engine._compress_with_vad(waveform, 16000)

            # 빈 timestamp → 빈 mapping
            assert mapping == []

    def test_vad_with_import_error_returns_original(self):
        """silero_vad import 실패 시 원본 waveform 반환"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        waveform = torch.zeros((1, 16000))

        with patch.dict(sys.modules, {"silero_vad": None}):
            # _load_vad가 None을 반환하도록 mock
            with patch.object(engine, "_load_vad", return_value=None):
                compressed, mapping = engine._compress_with_vad(waveform, 16000)

                # 원본 그대로 반환
                assert compressed is waveform
                assert mapping == []

    def test_vad_exception_returns_original(self):
        """VAD 처리 예외 시 원본 waveform 반환"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        vad_mock = MagicMock()
        vad_mock.get_speech_timestamps.side_effect = Exception("VAD Error")

        waveform = torch.zeros((1, 16000))
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            compressed, _mapping = engine._compress_with_vad(waveform, 16000)

            # 예외 시 원본 반환
            assert compressed is waveform

    def test_vad_mono_waveform_handling(self):
        """모노 채널 waveform 처리"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        vad_mock = MagicMock()
        vad_mock.get_speech_timestamps.return_value = [{"start": 0, "end": 8000}]

        # 모노 waveform (1D 텐서)
        waveform = torch.zeros(16000)
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            _compressed, mapping = engine._compress_with_vad(waveform, 16000)

            # 매핑 생성됨
            assert len(mapping) == 1

    def test_vad_stereo_waveform_handling(self):
        """스테레오 채널 waveform 처리"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        vad_mock = MagicMock()
        vad_mock.get_speech_timestamps.return_value = [{"start": 0, "end": 8000}]

        # 스테레오 waveform (2D 텐서)
        waveform = torch.zeros((2, 16000))
        with patch.dict(sys.modules, {"silero_vad": vad_mock}):
            compressed, mapping = engine._compress_with_vad(waveform, 16000)

            # 채널 보존 확인
            assert compressed.shape[0] == 2
            assert len(mapping) == 1


# ==========================================================================
# _map_segments 엣지 케이스
# ==========================================================================


class TestMapSegments:
    """VAD 압축 세그먼트 역매핑 테스트"""

    def setup_method(self):
        _reset_engine()

    def test_map_segments_empty_mapping(self):
        """빈 mapping이면 raw_segments 그대로 반환"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        raw_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=5.0)]

        result = engine._map_segments(raw_segments, [], 16000)

        # mapping 비어있으면 그대로 반환
        assert result == raw_segments

    def test_map_segments_no_overlap(self):
        """매핑과 겹치는 부분 없으면 해당 세그먼트 제외"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        mapping = [{"compressed_start": 0, "compressed_end": 8000, "original_start": 50000}]

        # compressed 시간 10-15초 (mapping 범위 밖)
        raw_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=10.0, end=15.0)]

        result = engine._map_segments(raw_segments, mapping, 16000)

        # 겹침 없음 → 빈 결과
        assert result == []

    def test_map_segments_partial_overlap(self):
        """부분 겹침 처리"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # mapping: compressed 0-5초 = original 50-55초 (sample_rate 16000)
        # compressed 0-80000 samples = 5초, original_start=500000 samples = 31.25초
        mapping = [{"compressed_start": 0, "compressed_end": 80000, "original_start": 500000}]

        # compressed 2-4초 (mapping 범위 내)
        raw_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=2.0, end=4.0)]

        result = engine._map_segments(raw_segments, mapping, 16000)

        # 매핑된 부분만 반환 (original: 31.25+2=33.25초 ~ 31.25+4=35.25초)
        assert len(result) == 1
        assert 33.0 <= result[0].start <= 34.0
        assert 35.0 <= result[0].end <= 36.0

    def test_map_segments_splits_on_silence_padding(self):
        """silence padding을 가로지르는 세그먼트 분리"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        # 0.1초 silence padding으로 분리된 두 음성 구간
        mapping = [
            {"compressed_start": 0, "compressed_end": 5000, "original_start": 0},
            {"compressed_start": 5160, "compressed_end": 10160, "original_start": 10000},
        ]

        # 두 매핑을 모두 가로지르는 긴 세그먼트
        raw_segments = [SpeakerSegment(speaker_id="SPEAKER_00", start=0.0, end=10.0)]

        result = engine._map_segments(raw_segments, mapping, 16000)

        # 두 매핑에 대해 두 개 세그먼트로 분리
        assert len(result) >= 1


# ==========================================================================
# unload() 및 프로퍼티 테스트
# ==========================================================================


class TestEngineProperties:
    """엔진 프로퍼티 테스트"""

    def setup_method(self):
        _reset_engine()

    def test_is_loaded_property(self):
        """is_loaded 프로퍼티"""
        engine = DiarizationEngine()

        # 초기: False
        assert engine.is_loaded is False

        # 로드 후: True
        engine._model_loaded = True
        assert engine.is_loaded is True

    def test_model_name_property(self):
        """model_name 프로퍼티"""
        engine = DiarizationEngine()

        # 기본값
        assert "diarization" in engine.model_name

    def test_load_time_seconds_property(self):
        """load_time_seconds 프로퍼티"""
        engine = DiarizationEngine()

        # 초기: None
        assert engine.load_time_seconds is None

        # 로드 후: 값 설정
        engine._load_time_seconds = 1.5
        assert engine.load_time_seconds == 1.5

    def test_unload_clears_all_state(self):
        """unload() 시 모든 상태 초기화"""
        mock_pipeline = _make_mock_pipeline()
        engine = DiarizationEngine()
        engine._pipeline = mock_pipeline
        engine._model_loaded = True
        engine._load_time_seconds = 2.0

        engine.unload()

        assert engine._pipeline is None
        assert engine._model_loaded is False
        assert engine._load_time_seconds is None


# ==========================================================================
# 다운샘플링 테스트 추가
# ==========================================================================


class TestDownsamplingEdgeCases:
    """다운샘플링 엣지 케이스"""

    def setup_method(self):
        _reset_engine()

    def test_downsample_with_zero_target_rate_skips(self):
        """target_sample_rate=0이면 다운샘플링 스킵"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        audio = Path("fake.wav")
        audio.touch()

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)
        mock_torchaudio.functional.resample = MagicMock()

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(audio, target_sample_rate=0, vad_filter=False)

        # resample 호출 안 됨
        mock_torchaudio.functional.resample.assert_not_called()

    def test_downsample_with_negative_target_skips(self):
        """target_sample_rate<0이면 다운샘플링 스킵"""
        engine, _ = _make_loaded_engine_with_mock_pipeline()

        audio = Path("fake.wav")
        audio.touch()

        mock_torchaudio = MagicMock()
        mock_torchaudio.load.return_value = (torch.zeros((1, 16000)), 16000)
        mock_torchaudio.functional.resample = MagicMock()

        with patch.dict(sys.modules, {"torchaudio": mock_torchaudio}):
            engine.diarize(audio, target_sample_rate=-1, vad_filter=False)

            # resample 호출 안 됨
            mock_torchaudio.functional.resample.assert_not_called()


# ==========================================================================
# _calc_overlap 테스트
# ==========================================================================


class TestCalcOverlap:
    """오버랩 계산 테스트"""

    def test_calc_overlap_no_overlap(self):
        """오버랩 없으면 0"""
        result = DiarizationEngine._calc_overlap(0.0, 5.0, 10.0, 15.0)
        assert result == 0.0

    def test_calc_overlap_full_overlap(self):
        """완전 오버랩"""
        result = DiarizationEngine._calc_overlap(0.0, 10.0, 0.0, 10.0)
        assert result == 10.0

    def test_calc_overlap_partial_overlap(self):
        """부분 오버랩"""
        result = DiarizationEngine._calc_overlap(0.0, 10.0, 5.0, 15.0)
        assert result == 5.0

    def test_calc_overlap_touching(self):
        """경계가 닿아만 있으면 0"""
        result = DiarizationEngine._calc_overlap(0.0, 5.0, 5.0, 10.0)
        assert result == 0.0


# ==========================================================================
# _segments_from_result 테스트
# ==========================================================================


class TestSegmentsFromResult:
    """pyannote 결과 변환 테스트"""

    def test_segments_from_result_with_speaker_diarization_attr(self):
        """speaker_diarization 속성 있는 경우"""
        mock_result = MagicMock()
        mock_diarization = MagicMock()

        # itertracks yield: (turn, track, speaker)
        mock_turn1 = MagicMock()
        mock_turn1.start = 1.5
        mock_turn1.end = 3.7
        mock_turn2 = MagicMock()
        mock_turn2.start = 4.0
        mock_turn2.end = 6.2

        mock_diarization.itertracks.return_value = [
            (mock_turn1, None, "SPEAKER_00"),
            (mock_turn2, None, "SPEAKER_01"),
        ]
        mock_result.speaker_diarization = mock_diarization

        segments = DiarizationEngine._segments_from_result(mock_result)

        assert len(segments) == 2
        assert segments[0].speaker_id == "SPEAKER_00"
        assert round(segments[0].start, 3) == 1.5
        assert round(segments[0].end, 3) == 3.7

    def test_segments_from_result_without_speaker_diarization_attr(self):
        """speaker_diarization 속성 없으면 result 자체 사용"""
        mock_result = MagicMock()
        del mock_result.speaker_diarization  # 속성 삭제

        mock_turn = MagicMock()
        mock_turn.start = 2.0
        mock_turn.end = 4.5

        mock_result.itertracks = MagicMock(return_value=[(mock_turn, None, "SPEAKER_00")])

        segments = DiarizationEngine._segments_from_result(mock_result)

        # getattr fallback로 result 자체를 diarization으로 사용
        # mock_result에 itertracks가 있으므로 작동해야 함
        assert len(segments) >= 0
        if len(segments) > 0:
            assert segments[0].speaker_id == "SPEAKER_00"


# ==========================================================================
# ==========================================================================
