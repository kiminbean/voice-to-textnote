"""
회의록 포맷터 - DiarizedSegmentResult → MinutesSegment 변환
REQ-MIN-001: 연속 같은 화자 세그먼트 병합
REQ-MIN-002: 화자 통계 계산 (total_speaking_time, segment_count, speaking_ratio)
REQ-MIN-003: 마크다운 출력 형식: **[HH:MM:SS] Speaker N**: text
REQ-MIN-004: JSON 구조화 출력
REQ-MIN-005: speaker_id=None → "Unknown Speaker"
REQ-MIN-016: 자동 이름 생성 SPEAKER_00 → "Speaker 1"
REQ-MIN-017: speaker_names 매핑 우선 적용
"""

from backend.schemas.diarization import DiarizedSegmentResult
from backend.schemas.minutes import MinutesSegment, SpeakerStats
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MinutesFormatter:
    """
    화자 분리 결과를 회의록으로 변환하는 포맷터

    사용법:
        formatter = MinutesFormatter(speaker_names={"SPEAKER_00": "김팀장"})
        segments = formatter.format_minutes(diarized_segments)
        markdown = formatter.to_markdown(segments)
        stats = formatter.calculate_speaker_stats(segments, total_duration=120.0)
    """

    # 알 수 없는 화자 기본 이름 (REQ-MIN-005)
    UNKNOWN_SPEAKER_NAME = "Unknown Speaker"

    def __init__(self, speaker_names: dict[str, str] | None = None) -> None:
        """
        Args:
            speaker_names: 화자 ID → 표시 이름 매핑 (REQ-MIN-017)
                           None이면 자동 생성 (REQ-MIN-016)
        """
        # 사용자 정의 이름 매핑 저장
        self._speaker_names = speaker_names or {}
        # 자동 생성 이름 캐시 (SPEAKER_00 → "Speaker 1" 등)
        self._auto_name_cache: dict[str, str] = {}
        # 화자 등장 순서 추적 (자동 번호 부여용)
        self._speaker_order: list[str] = []

    def format_minutes(
        self, diarized_segments: list[DiarizedSegmentResult]
    ) -> list[MinutesSegment]:
        """
        DiarizedSegmentResult 목록을 MinutesSegment 목록으로 변환 (REQ-MIN-001)
        연속된 같은 화자 세그먼트는 하나로 병합

        Args:
            diarized_segments: 화자 분리 결과 세그먼트 목록

        Returns:
            병합된 MinutesSegment 목록
        """
        if not diarized_segments:
            return []

        result: list[MinutesSegment] = []
        # 현재 병합 중인 세그먼트 그룹
        current_group: list[DiarizedSegmentResult] = []

        for seg in diarized_segments:
            if not current_group:
                # 첫 번째 세그먼트: 그룹 시작
                current_group.append(seg)
            elif seg.speaker_id == current_group[0].speaker_id:
                # 같은 화자 연속 → 그룹에 추가 (REQ-MIN-001)
                current_group.append(seg)
            else:
                # 화자 변경 → 현재 그룹을 MinutesSegment로 변환 후 새 그룹 시작
                result.append(self._merge_group(current_group))
                current_group = [seg]

        # 마지막 그룹 처리
        if current_group:
            result.append(self._merge_group(current_group))

        return result

    def calculate_speaker_stats(
        self,
        segments: list[MinutesSegment],
        total_duration: float,
    ) -> list[SpeakerStats]:
        """
        화자별 통계 계산 (REQ-MIN-002)
        speaker_id=None(Unknown Speaker)은 통계에서 제외

        Args:
            segments: MinutesSegment 목록 (format_minutes() 결과)
            total_duration: 전체 대화 시간 (초), ZeroDivision 방지

        Returns:
            화자별 SpeakerStats 목록
        """
        if not segments:
            return []

        # 화자별 발화 시간/세그먼트 수 집계
        stats_map: dict[str, dict] = {}
        for seg in segments:
            # speaker_id=None(Unknown Speaker)은 제외
            if seg.speaker_id is None:
                continue

            if seg.speaker_id not in stats_map:
                stats_map[seg.speaker_id] = {
                    "speaker_id": seg.speaker_id,
                    "speaker_name": seg.speaker_name,
                    "total_speaking_time": 0.0,
                    "segment_count": 0,
                }
            stats_map[seg.speaker_id]["total_speaking_time"] += seg.end - seg.start
            stats_map[seg.speaker_id]["segment_count"] += 1

        if not stats_map:
            return []

        # speaking_ratio 계산 (ZeroDivision 방지)
        result = []
        for speaker_data in stats_map.values():
            speaking_time = speaker_data["total_speaking_time"]
            # total_duration=0이면 비율=0 (REQ-MIN-002)
            ratio = (speaking_time / total_duration * 100.0) if total_duration > 0 else 0.0
            result.append(
                SpeakerStats(
                    speaker_id=speaker_data["speaker_id"],
                    speaker_name=speaker_data["speaker_name"],
                    total_speaking_time=speaking_time,
                    segment_count=speaker_data["segment_count"],
                    speaking_ratio=round(ratio, 2),
                )
            )

        return result

    def to_markdown(self, segments: list[MinutesSegment]) -> str:
        """
        MinutesSegment 목록을 마크다운 형식으로 변환 (REQ-MIN-003)
        형식: **[HH:MM:SS] Speaker N**: text

        Args:
            segments: MinutesSegment 목록

        Returns:
            마크다운 형식 회의록 문자열
        """
        if not segments:
            return ""

        lines = []
        for seg in segments:
            # 시작 시간을 HH:MM:SS 형식으로 변환
            time_str = self._seconds_to_hhmmss(seg.start)
            line = f"**[{time_str}] {seg.speaker_name}**: {seg.text}"
            lines.append(line)

        return "\n".join(lines)

    def _merge_group(self, group: list[DiarizedSegmentResult]) -> MinutesSegment:
        """
        같은 화자의 연속 세그먼트 그룹을 하나의 MinutesSegment로 병합

        Args:
            group: 같은 화자의 DiarizedSegmentResult 목록 (비어있지 않음)

        Returns:
            병합된 MinutesSegment
        """
        first = group[0]
        last = group[-1]

        # 텍스트 결합: 공백으로 연결
        merged_text = " ".join(seg.text for seg in group)

        # 화자 이름 결정
        speaker_name = self._get_speaker_name(first.speaker_id)

        return MinutesSegment(
            speaker_id=first.speaker_id,
            speaker_name=speaker_name,
            text=merged_text,
            start=first.start,
            end=last.end,
        )

    def _get_speaker_name(self, speaker_id: str | None) -> str:
        """
        speaker_id에 대응하는 표시 이름 반환

        우선순위:
        1. speaker_id=None → "Unknown Speaker" (REQ-MIN-005)
        2. 사용자 정의 speaker_names 매핑 (REQ-MIN-017)
        3. 자동 생성 이름 (REQ-MIN-016): SPEAKER_00 → "Speaker 1"

        Args:
            speaker_id: 화자 ID (None 가능)

        Returns:
            화자 표시 이름
        """
        # None이면 Unknown Speaker (REQ-MIN-005)
        if speaker_id is None:
            return self.UNKNOWN_SPEAKER_NAME

        # 사용자 정의 이름 우선 적용 (REQ-MIN-017)
        if speaker_id in self._speaker_names:
            if speaker_id not in self._speaker_order:
                self._speaker_order.append(speaker_id)
            return self._speaker_names[speaker_id]

        # 자동 생성 이름 캐시 확인 (REQ-MIN-016)
        if speaker_id in self._auto_name_cache:
            return self._auto_name_cache[speaker_id]

        # 처음 등장하는 화자: 등장 순서에 따라 번호 부여
        if speaker_id not in self._speaker_order:
            self._speaker_order.append(speaker_id)

        speaker_number = self._speaker_order.index(speaker_id) + 1
        auto_name = f"Speaker {speaker_number}"
        self._auto_name_cache[speaker_id] = auto_name

        logger.debug("화자 이름 자동 생성", speaker_id=speaker_id, name=auto_name)
        return auto_name

    @staticmethod
    def _seconds_to_hhmmss(seconds: float) -> str:
        """
        초를 HH:MM:SS 형식으로 변환 (REQ-MIN-003)

        Args:
            seconds: 초 단위 시간

        Returns:
            "HH:MM:SS" 형식 문자열
        """
        total_seconds = int(seconds)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
