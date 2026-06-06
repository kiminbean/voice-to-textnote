"""
회의 감성 분석 서비스
"""

import re
from collections import defaultdict
from typing import Literal

import numpy as np

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SentimentService:
    """회의 감성 분석 서비스"""

    # 감성 단어 사전 (한국어)
    POSITIVE_WORDS = {
        "좋아", "훌륭", "대단", "완벽", "만족", "감사", "최고", "짱", "굿", "좋음",
        "성공", "극대화", "효과적", "생산적", "협력", "기여", "창의적", "혁신",
        "발전", "성장", "긍정", "호기심", "열정", "자신감", "유능", "전문",
        "정확", "신속", "체계", "효율", "안정", "신뢰", "대화", "소통",
        "이해", "공감", "지지", "동의", "찬성", "적극", "적응", "유연",
        "문해", "혁신적", "프로", "완벽한", "훌륭한", "뛰어난", "특별한"
    }

    NEGATIVE_WORDS = {
        "나쁘", "싫어", "실망", "불만", "문제", "오류", "실패", "약점", "부족",
        "지연", "어려움", "고통", "스트레스", "압박", "불안", "우려", "의심",
        "반대", "거부", "저항", "충돌", "마찰", "갈등", "대립", "비판",
        "불만족", "불이익", "위험", "손실", "손해", "차질", "혼란", "복잡",
        "비효율", "저조", "부진", "불안정", "불신", "원망", "불평", "불화",
        "갈등", "마찰", "대립", "갈등", "문제", "장애", "핸디캡", "제약",
        "한계", "부정", "회의적", "냉소적", "비관적", "무기력", "피로", "지침"
    }

    # 감성 강도 조정어
    INTENSIFIERS = {
        "매우", "아주", "정말", "완전히", "극적으로", "특히", "더욱", "높게", "크게"
    }

    NEGATORS = {
        "안", "못", "지 않", "아니", "전혀", "조금도", "결코", "아예"
    }

    def __init__(self):
        """초기화"""
        self.word_sentiment = {}
        for word in self.POSITIVE_WORDS:
            self.word_sentiment[word] = 1.0
        for word in self.NEGATIVE_WORDS:
            self.word_sentiment[word] = -1.0

    def calculate_sentence_sentiment(self, text: str) -> float:
        """
        문장의 감성 점수 계산 (-1.0 ~ 1.0)

        Args:
            text: 분할할 텍스트

        Returns:
            float: 감성 점수 (-1.0=매우 부정, 1.0=매우 긍정)
        """
        if not text or not text.strip():
            return 0.0

        # 토큰화 (간단한 한국어 분할)
        words = re.findall(r'\b\w+\b', text.lower())

        if not words:  # pragma: no cover
            return 0.0

        sentiment_score = 0.0
        negation_active = False
        intensifier_active = False

        for word in words:
            # 부정 처리
            if any(neg in word for neg in self.NEGATORS):
                negation_active = True
                continue

            # 강조 처리
            if any(intens in word for intens in self.INTENSIFIERS):
                intensifier_active = True
                continue

            # 감성 단어 점수 계산
            if word in self.word_sentiment:
                score = self.word_sentiment[word]

                # 강조어 적용  # pragma: no cover
                if intensifier_active:
                    score *= 1.5  # pragma: no cover
                    intensifier_active = False  # pragma: no cover

                # 부정 적용
                if negation_active:
                    score *= -1  # pragma: no cover
                    negation_active = False  # pragma: no cover

                sentiment_score += score

        # 정규화 (-1.0 ~ 1.0)
        if len(words) > 0:
            sentiment_score = max(-1.0, min(1.0, sentiment_score / len(words)))

        return sentiment_score

    async def analyze_meeting_sentiment(self, segments: list[dict]) -> dict:
        """
        회의록 전체의 감성 분석

        Args:
            segments: 발화 세그먼트 목록

        Returns:
            dict: 감성 분석 결과
        """
        if not segments:
            return self._empty_sentiment_result()

        sentiment_scores = []
        positive_count = 0
        neutral_count = 0
        negative_count = 0

        for segment in segments:
            text = str(segment.get("text", "") or "").strip()
            if text:
                score = self.calculate_sentence_sentiment(text)
                sentiment_scores.append(score)

                if score > 0.1:
                    positive_count += 1
                elif score < -0.1:
                    negative_count += 1
                else:
                    neutral_count += 1

        if not sentiment_scores:
            return self._empty_sentiment_result()

        # 감성 점수 비율 계산
        total_segments = len(sentiment_scores)
        positive_ratio = positive_count / total_segments
        neutral_ratio = neutral_count / total_segments
        negative_ratio = negative_count / total_segments

        # 종합 감성 점수 (가중 평균)
        overall_score = np.mean(sentiment_scores)

        # 주요 감성 판별
        if positive_ratio > negative_ratio and positive_ratio > neutral_ratio:
            dominant = "positive"
        elif negative_ratio > positive_ratio and negative_ratio > neutral_ratio:
            dominant = "negative"
        else:
            dominant = "neutral"

        return {
            "positive": round(positive_ratio, 3),
            "neutral": round(neutral_ratio, 3),
            "negative": round(negative_ratio, 3),
            "dominant": dominant,
            "overall_score": round(overall_score, 3),
        }

    def _empty_sentiment_result(self) -> dict:
        """비어있는 감성 결과 반환"""
        return {
            "positive": 0.0,
            "neutral": 1.0,
            "negative": 0.0,
            "dominant": "neutral",
            "overall_score": 0.0,
        }

    async def extract_key_phrases_with_sentiment(self, segments: list[dict]) -> dict[str, float]:
        """
        주요 키워드 추출 및 감성 점수 부여

        Args:
            segments: 발화 세그먼트 목록

        Returns:
            dict: 키워드별 감성 점수
        """
        key_phrase_scores = defaultdict(list)

        # 키워드 추출 패턴 (2-3음절 단어)
        keyword_pattern = re.compile(r'\b\w{2,4}\b')

        for segment in segments:
            text = str(segment.get("text", "") or "")
            if text:
                words = keyword_pattern.findall(text.lower())

                for word in words:
                    if len(word) >= 2:  # 최소 2음절
                        score = self.calculate_sentence_sentiment(text)
                        key_phrase_scores[word].append(score)

        # 키워드별 평균 점수 계산
        result = {}
        for phrase, scores in key_phrase_scores.items():
            if scores:  # 점수가 있는 경우만
                avg_score = sum(scores) / len(scores)
                result[phrase] = round(avg_score, 3)

        # 점수 순으로 정렬 (상위 20개)
        sorted_result = dict(sorted(result.items(), key=lambda x: x[1], reverse=True)[:20])
        return sorted_result

    def calculate_trend_direction(self, segments: list[dict]) -> Literal["improving", "declining", "stable"]:
        """
        회의 진행 방향에 따른 감성 추이 계산

        Args:
            segments: 시간순 정렬된 발화 세그먼트 목록

        Returns:
            Literal["improving", "declining", "stable"]: 추이 방향
        """
        if len(segments) < 3:
            return "stable"

        # 시간순으로 점수 계산
        time_points = []
        for segment in segments:
            text = str(segment.get("text", "") or "")
            if text:
                score = self.calculate_sentence_sentiment(text)
                start_time = float(segment.get("start", 0) or 0)
                time_points.append((start_time, score))

        if not time_points:  # pragma: no cover
            return "stable"

        # 전반부 vs 후반부 비교
        mid_point = len(time_points) // 2
        early_scores = [score for _, score in time_points[:mid_point]]
        late_scores = [score for _, score in time_points[mid_point:]]

        if not early_scores or not late_scores:
            return "stable"

        early_avg = sum(early_scores) / len(early_scores)
        late_avg = sum(late_scores) / len(late_scores)

        # 차이가 0.1 이상이면 추이로 판별
        diff = late_avg - early_avg
        if diff > 0.1:
            return "improving"
        elif diff < -0.1:
            return "declining"
        else:
            return "stable"

    def calculate_overall_trend(self, sentiment_scores: list[float]) -> Literal["improving", "declining", "stable"]:
        """
        전체 감성 추이 계산

        Args:
            sentiment_scores: 각 회의의 감성 점수 목록

        Returns:
            Literal["improving", "declining", "stable"]: 추이 방향
        """
        if len(sentiment_scores) < 2:
            return "stable"

        # 선형 회귀 기울기 계산
        x = list(range(len(sentiment_scores)))
        n = len(sentiment_scores)

        sum_x = sum(x)
        sum_y = sum(sentiment_scores)
        sum_xy = sum(xi * yi for xi, yi in zip(x, sentiment_scores))
        sum_x2 = sum(xi * xi for xi in x)

        # 기울기 계산: slope = (n*Σxy - Σx*Σy) / (n*Σx2 - (Σx)²)
        numerator = n * sum_xy - sum_x * sum_y
        denominator = n * sum_x2 - sum_x * sum_x

        if denominator == 0:  # pragma: no cover
            return "stable"

        slope = numerator / denominator

        # 기울기에 따른 추이 판별
        if slope > 0.05:
            return "improving"
        elif slope < -0.05:
            return "declining"
        else:
            return "stable"

    async def analyze_historical_trends(self, meeting_data_list: list[dict]) -> list[dict]:
        """
        역사적 감성 추이 분석

        Args:
            meeting_data_list: 회의 데이터 목록

        Returns:
            list[dict]: 감성 추이 데이터
        """
        trends = []

        for meeting_data in meeting_data_list:
            segments = meeting_data.get("segments", [])
            if segments:
                analysis = await self.analyze_meeting_sentiment(segments)
                meeting_id = meeting_data.get("meeting_id", meeting_data.get("task_id", "unknown"))
                created_at = meeting_data.get("created_at", meeting_data.get("timestamp", ""))

                trends.append({
                    "meeting_id": meeting_id,
                    "created_at": created_at,
                    "sentiment_score": analysis["overall_score"],
                    "positive_ratio": analysis["positive"],
                    "negative_ratio": analysis["negative"],
                    "neutral_ratio": analysis["neutral"],
                    "segments_count": len(segments),
                })

        # 시간순 정렬
        trends.sort(key=lambda x: x.get("created_at", ""))
        return trends

    async def get_speaker_segments(self, speaker_id: str, meeting_ids: list[str] | None = None) -> list[dict]:
        """
        특정 화자의 세그먼트 조회

        Args:
            speaker_id: 화자 ID
            meeting_ids: 특정 회의 ID 목록 (None이면 전체)

        Returns:
            list[dict]: 화자 세그먼트 목록
        """
        # 이 메서드는 데이터베이스 의존성이 있으나, 현재는 샘플 구현
        # 실제 구현에서는 DB 쿼리를 수행해야 합니다.
        # 여기서는 예시로 빈 리스트 반환
        return []

    async def analyze_speaker_sentiment(self, segments: list[dict]) -> dict:
        """
        화자별 감성 분석

        Args:
            segments: 화자 세그먼트 목록

        Returns:
            dict: 화자 감성 분석 결과
        """
        if not segments:
            return {
                "speaker_name": "알 수 없음",
                "overall_score": 0.0,
                "positive_ratio": 0.0,
                "negative_ratio": 0.0,
            }

        analysis = await self.analyze_meeting_sentiment(segments)
        total_segments = len(segments)
        positive_segments = sum(1 for s in segments if analysis["positive"] > 0)
        negative_segments = sum(1 for s in segments if analysis["negative"] > 0)

        return {
            "speaker_name": segments[0].get("speaker", "알 수 없음"),
            "overall_score": analysis["overall_score"],
            "positive_ratio": positive_segments / total_segments if total_segments > 0 else 0.0,
            "negative_ratio": negative_segments / total_segments if total_segments > 0 else 0.0,
        }
