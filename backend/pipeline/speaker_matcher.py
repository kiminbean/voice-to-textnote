"""
화자 매칭 파이프라인 - STT 세그먼트와 화자 분리 결과 타임스탬프 겹침 매칭
REQ-DIA-003: 타임스탬프 겹침 기반 화자 할당
REQ-DIA-004: speaker_confidence = overlap_time / segment_duration
REQ-DIA-005: 동점 시 가장 빠른 시작 시간 화자 선택 + 경고 로그
REQ-DIA-006: 겹침 없음 → speaker_id=None, speaker_confidence=0.0
"""

from typing import NamedTuple

from backend.schemas.diarization import DiarizedSegmentResult
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SpeakerSegment(NamedTuple):
    """화자 분리 결과 단일 세그먼트"""

    speaker_id: str
    start: float  # 시작 시간 (초)
    end: float  # 종료 시간 (초)


class SpeakerMatcher:
    """
    STT 세그먼트와 화자 분리 결과를 타임스탬프 겹침으로 매칭

    알고리즘:
    - 각 STT 세그먼트에 대해 모든 화자 세그먼트와의 겹침 시간 계산
    - 가장 큰 겹침을 가진 화자를 할당
    - 동점(same overlap)이면 시작 시간이 더 빠른 화자 선택 + WARNING 로그
    - 겹침이 없으면 speaker_id=None, speaker_confidence=0.0
    """

    def match(
        self,
        stt_segments: list[dict],
        dia_segments: list[SpeakerSegment],
    ) -> list[DiarizedSegmentResult]:
        """
        STT 세그먼트 목록에 화자 ID를 매핑하여 DiarizedSegmentResult 리스트 반환

        Args:
            stt_segments: STT 결과 딕셔너리 목록 (id, start, end, text, confidence)
            dia_segments: 화자 분리 세그먼트 목록 (SpeakerSegment NamedTuple)

        Returns:
            DiarizedSegmentResult 리스트
        """
        if not stt_segments:
            return []

        results = []
        for stt_seg in stt_segments:
            speaker_id, speaker_confidence = self._find_best_speaker(stt_seg, dia_segments)
            results.append(
                DiarizedSegmentResult(
                    id=stt_seg["id"],
                    start=stt_seg["start"],
                    end=stt_seg["end"],
                    text=stt_seg["text"],
                    confidence=stt_seg.get("confidence", 0.0),
                    speaker_id=speaker_id,
                    speaker_confidence=speaker_confidence,
                )
            )
        return results

    def _find_best_speaker(
        self,
        stt_seg: dict,
        dia_segments: list[SpeakerSegment],
    ) -> tuple[str | None, float]:
        """
        STT 세그먼트에 가장 잘 맞는 화자를 겹침 시간으로 찾음

        Returns:
            (speaker_id, speaker_confidence) 튜플
            겹침 없으면 (None, 0.0)
        """
        stt_start = stt_seg["start"]
        stt_end = stt_seg["end"]
        stt_duration = stt_end - stt_start

        # 세그먼트 길이가 0이면 신뢰도 0으로 처리
        if stt_duration <= 0:
            return None, 0.0

        # 각 화자 세그먼트와 겹침 계산
        overlaps: list[tuple[float, float, str]] = []  # (overlap_time, start, speaker_id)
        for dia_seg in dia_segments:
            overlap = self._calc_overlap(stt_start, stt_end, dia_seg.start, dia_seg.end)
            if overlap > 0:
                overlaps.append((overlap, dia_seg.start, dia_seg.speaker_id))

        if not overlaps:
            return None, 0.0

        # 최대 겹침 찾기 (동점 시 빠른 시작 시간)
        best_overlap = max(overlaps, key=lambda x: (x[0], -x[1]))
        max_overlap_time = best_overlap[0]

        # 동점 확인 - 동일한 최대 겹침 값이 여러 개인 경우
        top_overlaps = [o for o in overlaps if o[0] == max_overlap_time]
        if len(top_overlaps) > 1:
            # 동점: 가장 빠른 시작 시간 선택
            best_overlap = min(top_overlaps, key=lambda x: x[1])
            logger.warning(
                "화자 매칭 동점 발생: 가장 빠른 시작 시간의 화자 선택",
                segment_start=stt_start,
                segment_end=stt_end,
                candidates=[o[2] for o in top_overlaps],
                selected=best_overlap[2],
            )

        selected_speaker = best_overlap[2]
        confidence = max_overlap_time / stt_duration

        return selected_speaker, round(min(1.0, confidence), 6)

    @staticmethod
    def _calc_overlap(a_start: float, a_end: float, b_start: float, b_end: float) -> float:
        """
        두 구간 [a_start, a_end)와 [b_start, b_end)의 겹침 시간 계산

        Returns:
            겹침 시간 (초), 겹침 없으면 0.0
        """
        overlap_start = max(a_start, b_start)
        overlap_end = min(a_end, b_end)
        return max(0.0, overlap_end - overlap_start)
