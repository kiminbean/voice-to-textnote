"""
회의 감정 분석기 - OpenAI API 기반
SPEC-SENTIMENT-001: 화자별 발화 구간 감정 분석
- 텍스트 기반 감정 분석 (positive/neutral/negative + 세부 감정)
- 화자별 감정 요약 통계
- 감정 변화 타임라인 생성
"""

import json
import re
from collections import Counter

from openai import OpenAI

from backend.schemas.sentiment import (
    SentimentResult,
    SentimentSegment,
    SpeakerSentiment,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)

# 지원 감정 레이블
EMOTION_LABELS = [
    "joy", "satisfaction", "interest", "neutral",
    "frustration", "anger", "sadness", "surprise", "anxiety", "confusion",
]

VALID_SENTIMENTS = {"positive", "neutral", "negative"}


class SentimentAnalyzer:
    """OpenAI API를 사용하여 회의 감정 분석을 수행하는 클래스"""

    JSON_FORMAT_INSTRUCTION = (
        '다음 JSON 형식으로 응답하세요: {"segments": [...], "overall_sentiment": "...", "overall_emotion": "..."} '
        '각 segment는 {"start": float, "end": float, "speaker": "...", "text": "...", '
        '"sentiment": "positive|neutral|negative", "emotion": "...", "confidence": float} 형식입니다.'
    )

    def build_prompt(self, segments: list[dict], speaker_stats: list[dict]) -> str:
        """회의록 세그먼트를 기반으로 감정 분석 프롬프트 생성"""

        # 대화 내용
        dialogue_lines = []
        for seg in segments:
            speaker = seg.get("speaker_name", "알 수 없음")
            text = seg.get("text", "")
            start = seg.get("start", 0.0)
            end = seg.get("end", 0.0)
            dialogue_lines.append(
                f"[{start:.1f}-{end:.1f}] {speaker}: {text}"
            )
        dialogue_section = "\n".join(dialogue_lines) if dialogue_lines else "대화 내용 없음"

        # 화자 정보
        stats_lines = []
        for stat in speaker_stats:
            name = stat.get("speaker_name", "알 수 없음")
            ratio = stat.get("speaking_ratio", 0.0)
            stats_lines.append(f"- {name}: 발화 비율 {ratio:.1f}%")
        stats_section = "\n".join(stats_lines) if stats_lines else "- 화자 정보 없음"

        prompt = f"""다음은 회의 녹취록입니다. 각 발화 구간의 감정을 분석해 주세요.

## 화자 정보
{stats_section}

## 회의 대화 내용
{dialogue_section}

## 분석 지시사항
1. 각 발화 구간의 감정을 분석하세요:
   - sentiment: positive / neutral / negative (3가지만)
   - emotion: joy, satisfaction, interest, neutral, frustration, anger, sadness, surprise, anxiety, confusion 중 선택
   - confidence: 0.0~1.0 (분석 신뢰도)

2. 회의 전체 감정(overall_sentiment)과 주요 감정(overall_emotion)도 판단하세요.

3. 주의사항:
   - 비즈니스 회의 맥락을 고려하세요. "문제"라는 단어가 반드시 부정적인 것은 아닙니다.
   - 한국어 뉘앙스를 정확히 파악하세요. (존댓말, 반말, 반어법 등)
   - 질문은 neutral로 분류하되, 불만이 섞인 질문은 negative로 분류하세요.

{self.JSON_FORMAT_INSTRUCTION}

[중요] JSON 안에 주석(// ...)을 절대 넣지 마세요. 순수 JSON만 출력하세요."""

        return prompt

    def parse_response(self, response_text: str) -> SentimentResult:
        """API 응답 텍스트를 SentimentResult로 파싱"""
        try:
            cleaned = response_text.strip()
            if cleaned.startswith("```"):
                first_newline = cleaned.index("\n")
                cleaned = cleaned[first_newline + 1:]
                if cleaned.rstrip().endswith("```"):
                    cleaned = cleaned.rstrip()[:-3].rstrip()

            cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
            data = json.loads(cleaned)

            # 세그먼트 파싱
            raw_segments = data.get("segments", [])
            segments: list[SentimentSegment] = []
            for seg in raw_segments:
                if not isinstance(seg, dict):
                    continue
                sentiment = seg.get("sentiment", "neutral")
                if sentiment not in VALID_SENTIMENTS:
                    sentiment = "neutral"
                segments.append(SentimentSegment(
                    start=seg.get("start", 0.0),
                    end=seg.get("end", 0.0),
                    speaker=seg.get("speaker", "알 수 없음"),
                    text=seg.get("text", ""),
                    sentiment=sentiment,
                    emotion=seg.get("emotion", "neutral"),
                    confidence=min(1.0, max(0.0, seg.get("confidence", 0.0))),
                ))

            # 화자별 통계 계산
            speakers = self._compute_speaker_stats(segments)

            # 감정 타임라인
            timeline = [
                {
                    "time": seg.start,
                    "sentiment": seg.sentiment,
                    "emotion": seg.emotion,
                    "speaker": seg.speaker,
                }
                for seg in segments
            ]

            return SentimentResult(
                overall_sentiment=data.get("overall_sentiment", "neutral"),
                overall_emotion=data.get("overall_emotion", "neutral"),
                segments=segments,
                speakers=speakers,
                emotional_timeline=timeline,
            )

        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning(
                "감정 분석 응답 JSON 파싱 실패",
                error=str(exc),
                response_preview=response_text[:200],
            )
            return SentimentResult()

    def _compute_speaker_stats(self, segments: list[SentimentSegment]) -> list[SpeakerSentiment]:
        """세그먼트에서 화자별 감정 통계 계산"""
        speaker_map: dict[str, list[SentimentSegment]] = {}
        for seg in segments:
            speaker_map.setdefault(seg.speaker, []).append(seg)

        results: list[SpeakerSentiment] = []
        for speaker, segs in speaker_map.items():
            total = len(segs)
            pos = sum(1 for s in segs if s.sentiment == "positive")
            neg = sum(1 for s in segs if s.sentiment == "negative")
            neu = total - pos - neg

            emotion_counter = Counter(s.emotion for s in segs)
            dominant = emotion_counter.most_common(1)[0][0] if emotion_counter else "neutral"

            results.append(SpeakerSentiment(
                speaker=speaker,
                total_segments=total,
                positive_ratio=round(pos / total, 3) if total else 0.0,
                neutral_ratio=round(neu / total, 3) if total else 0.0,
                negative_ratio=round(neg / total, 3) if total else 0.0,
                dominant_emotion=dominant,
                emotion_distribution=dict(emotion_counter),
            ))

        return results

    def analyze(
        self,
        segments: list[dict],
        speaker_stats: list[dict],
        api_key: str,
        model: str,
        max_tokens: int = 4096,
    ) -> SentimentResult:
        """OpenAI API를 호출하여 감정 분석 수행"""
        prompt = self.build_prompt(segments, speaker_stats)

        logger.info(
            "감정 분석 시작",
            model=model,
            max_tokens=max_tokens,
            segments_count=len(segments),
        )

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        response_text = response.choices[0].message.content

        logger.info(
            "감정 분석 API 응답 수신",
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
        )

        return self.parse_response(response_text)
