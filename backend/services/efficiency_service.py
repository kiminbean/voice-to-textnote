"""
회의 효율성 분석 서비스
"""

import json
import statistics
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.db.models import TaskResult, ActionItem
from backend.schemas.efficiency import (
    EfficiencyScoreResponse,
    EfficiencyMetrics,
    EfficiencyRecommendations,
    ParticipationMetric,
    DecisionMetric,
    ActionItemMetric,
    TimeDistributionMetric,
    KeywordMetric,
    SentimentTrend,
    Recommendation,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EfficiencyService:
    """회의 효율성 분석 서비스"""
    
    def __init__(self):
        self.keyword_patterns = {
            'decision': ['결정', '결정하다', '선택하다', '의결', '안건', '처리', '승인'],
            'action': ['해야', '할 것', '행동', '실행', '완료', '시작', '마감', '기한'],
            'discussion': ['논의', '토론', '검토', '보고', '공유', '설명']
        }
        
    async def analyze_meeting_efficiency(
        self,
        redis_client: aioredis.Redis,
        db: AsyncSession,
        task_id: str,
        include_recommendations: bool = True,
        min_speakers: int = 2,
        analysis_depth: str = "standard"
    ) -> EfficiencyScoreResponse:
        """회의 효율성 종합 분석"""
        
        # 1. 회의록 데이터 조회
        minutes_data = await self._get_minutes_data(redis_client, db, task_id)
        if minutes_data is None:
            raise ValueError(f"회의록 데이터를 찾을 수 없습니다: {task_id}")
        
        segments = minutes_data.get("segments", [])
        if not segments:
            raise ValueError("회의록 데이터에 segments 정보가 없습니다")
        
        # 2. 기본 지표 계산
        analysis_result = await self._calculate_basic_metrics(segments, analysis_depth)
        
        # 3. 세부 지표 계산
        participation_metrics = self._analyze_participation(segments, min_speakers)
        decision_metric = self._analyze_decisions(segments, analysis_depth)
        action_item_metric = self._analyze_action_items(segments, db, task_id)
        time_distribution = self._analyze_time_distribution(segments, analysis_depth)
        keyword_metric = self._analyze_keywords(segments)
        sentiment_trend = self._analyze_sentiment(segments) if analysis_depth == "detailed" else None
        
        # 4. 종합 효율성 점수 계산
        efficiency_metrics = self._calculate_efficiency_score(
            participation_metrics,
            decision_metric,
            action_item_metric,
            time_distribution,
            keyword_metric,
            sentiment_trend
        )
        
        # 5. 개선 제안 생성
        recommendations = None
        if include_recommendations:
            recommendations = self._generate_recommendations(
                efficiency_metrics,
                participation_metrics,
                time_distribution,
                analysis_depth
            )
        
        # 6. 최종 응답 생성
        return EfficiencyScoreResponse(
            task_id=task_id,
            analyzed_at=datetime.now(),
            analysis_depth=analysis_depth,
            efficiency_metrics=efficiency_metrics,
            recommendations=recommendations,
            meeting_duration_minutes=time_distribution.total_meeting_duration_minutes,
            total_speakers=len(participation_metrics),
            total_segments=len(segments),
            total_words=sum(len(seg.get("text", "").split()) for seg in segments)
        )
    
    async def _get_minutes_data(self, redis_client: aioredis.Redis, db: AsyncSession, task_id: str) -> Optional[Dict]:
        """회의록 데이터 조회 (Redis 우선)"""
        # Redis 조회
        redis_key = f"task:min:result:{task_id}"
        raw = await redis_client.get(redis_key)
        if raw:
            logger.debug("Redis 캐시 히트", key=redis_key)
            return json.loads(raw)
        
        # DB 폴백
        stmt = select(TaskResult).where(
            TaskResult.task_id == task_id,
            TaskResult.task_type == "minutes",
            TaskResult.status == "completed"
        )
        result = await db.execute(stmt)
        record = result.scalars().first()
        
        if record and record.result_data:
            logger.debug("DB 폴백 히트", task_id=task_id)
            return record.result_data
        
        return None
    
    def _calculate_basic_metrics(self, segments: List[Dict], analysis_depth: str) -> Dict:
        """기본 지표 계산"""
        if not segments:
            return {}
        
        total_duration = max(seg.get("end_time", 0) for seg in segments)
        total_words = sum(len(seg.get("text", "").split()) for seg in segments)
        unique_speakers = len(set(seg.get("speaker", "unknown") for seg in segments))
        
        return {
            "total_duration": total_duration,
            "total_words": total_words,
            "unique_speakers": unique_speakers,
            "avg_words_per_minute": total_words / (total_duration / 60) if total_duration > 0 else 0
        }
    
    def _analyze_participation(self, segments: List[Dict], min_speakers: int) -> List[ParticipationMetric]:
        """화자 참여도 분석"""
        speaker_stats = {}
        
        for seg in segments:
            speaker = seg.get("speaker", "unknown")
            text = seg.get("text", "")
            duration = seg.get("end_time", 0) - seg.get("start_time", 0)
            
            if speaker not in speaker_stats:
                speaker_stats[speaker] = {
                    "total_time": 0,
                    "segment_count": 0,
                    "total_words": 0
                }
            
            speaker_stats[speaker]["total_time"] += duration
            speaker_stats[speaker]["segment_count"] += 1
            speaker_stats[speaker]["total_words"] += len(text.split())
        
        total_meeting_time = sum(stats["total_time"] for stats in speaker_stats.values())
        participation_metrics = []
        
        for speaker, stats in speaker_stats.items():
            if len(speaker_stats) < min_speakers:
                continue
                
            speaking_percentage = (stats["total_time"] / total_meeting_time * 100) if total_meeting_time > 0 else 0
            avg_segment_length = stats["total_time"] / stats["segment_count"] if stats["segment_count"] > 0 else 0
            
            # 참여도 균형 점수 (참여 시간이 평균에 가까울수록 높음)
            avg_participation = total_meeting_time / len(speaker_stats)
            participation_balance_score = 1 - abs(stats["total_time"] - avg_participation) / avg_participation if avg_participation > 0 else 0
            participation_balance_score = max(0, participation_balance_score)
            
            participation_metrics.append(ParticipationMetric(
                speaker_id=speaker,
                speaker_name=speaker,
                speaking_time_seconds=int(stats["total_time"]),
                speaking_percentage=speaking_percentage,
                segment_count=stats["segment_count"],
                avg_segment_length=avg_segment_length,
                participation_balance_score=round(participation_balance_score, 2)
            ))
        
        return participation_metrics
    
    def _analyze_decisions(self, segments: List[Dict], analysis_depth: str) -> DecisionMetric:
        """결정 관련 분석"""
        decision_keywords = []
        decision_segments = []
        
        for i, seg in enumerate(segments):
            text = seg.get("text", "").lower()
            
            # 결정 관련 키워드 검색
            for keyword in self.keyword_patterns['decision']:
                if keyword in text:
                    decision_keywords.append({
                        "keyword": keyword,
                        "segment_index": i,
                        "speaker": seg.get("speaker", "unknown")
                    })
                    
                    # 해당 구간과 다음 구간을 결정 구간으로 간주
                    decision_segments.extend([i, i + 1] if i + 1 < len(segments) else [i])
        
        total_decisions = len(set(seg.get("speaker", "unknown") for seg in 
                                [segments[i] for i in decision_segments if i < len(segments)]))
        
        # 결정 속도 분석 (시간당 결정 수)
        total_duration = max(seg.get("end_time", 0) for seg in segments)
        decisions_per_hour = (total_decisions / (total_duration / 3600)) if total_duration > 0 else 0
        
        # 결정 명확도 점수
        decision_clarity_score = min(1.0, total_decisions / max(1, len(segments) / 10))
        
        # 결정 구간 평균 길이
        decision_times = [segments[i].get("end_time", 0) - segments[i].get("start_time", 0) 
                         for i in decision_segments if i < len(segments)]
        avg_decision_time = statistics.mean(decision_times) if decision_times else 0
        
        return DecisionMetric(
            total_decisions=total_decisions,
            decisions_per_hour=round(decisions_per_hour, 2),
            avg_decision_time_minutes=round(avg_decision_time / 60, 2),
            decision_clarity_score=round(decision_clarity_score, 2)
        )
    
    async def _analyze_action_items(self, segments: List[Dict], db: AsyncSession, task_id: str) -> ActionItemMetric:
        """액션 아이템 분석"""
        # DB에서 액션 아이템 조회
        stmt = select(ActionItem).where(ActionItem.task_id == task_id)
        result = await db.execute(stmt)
        action_items = result.scalars().all()
        
        total_action_items = len(action_items)
        
        # 시간당 액션 아이템 수
        total_duration = max(seg.get("end_time", 0) for seg in segments)
        action_items_per_hour = (total_action_items / (total_duration / 3600)) if total_duration > 0 else 0
        
        # 액션 아이템 명확도 점수
        clear_action_items = sum(1 for item in action_items 
                               if item.description and len(item.description.strip()) > 10)
        action_item_clarity_score = clear_action_items / max(1, total_action_items)
        
        return ActionItemMetric(
            total_action_items=total_action_items,
            action_items_per_hour=round(action_items_per_hour, 2),
            action_item_clarity_score=round(action_item_clarity_score, 2)
        )
    
    def _analyze_time_distribution(self, segments: List[Dict], analysis_depth: str) -> TimeDistributionMetric:
        """시간 분배 분석"""
        if not segments:
            return TimeDistributionMetric(
                total_meeting_duration_minutes=0,
                actual_speaking_time_minutes=0,
                silence_percentage=0,
                agenda_adherence_score=0.5,
                time_efficiency_score=0.5
            )
        
        total_meeting_duration = max(seg.get("end_time", 0) for seg in segments)
        actual_speaking_time = sum(seg.get("end_time", 0) - seg.get("start_time", 0) for seg in segments)
        silence_percentage = ((total_meeting_duration - actual_speaking_time) / total_meeting_duration * 100) if total_meeting_duration > 0 else 0
        
        # 안건 준수 점수 (시간대별 균등성)
        segment_durations = [seg.get("end_time", 0) - seg.get("start_time", 0) for seg in segments]
        if len(segment_durations) > 1:
            duration_variance = statistics.variance(segment_durations)
            agenda_adherence_score = max(0, 1 - (duration_variance / statistics.mean(segment_durations)) if statistics.mean(segment_durations) > 0 else 0.5)
        else:
            agenda_adherence_score = 0.5
        
        # 시간 효율성 점수 (실제 발화 시간 비율)
        time_efficiency_score = actual_speaking_time / total_meeting_duration if total_meeting_duration > 0 else 0
        
        return TimeDistributionMetric(
            total_meeting_duration_minutes=round(total_meeting_duration / 60, 2),
            actual_speaking_time_minutes=round(actual_speaking_time / 60, 2),
            silence_percentage=round(silence_percentage, 2),
            agenda_adherence_score=round(agenda_adherence_score, 2),
            time_efficiency_score=round(time_efficiency_score, 2)
        )
    
    def _analyze_keywords(self, segments: List[Dict]) -> KeywordMetric:
        """키워드 분석"""
        keyword_counts = {"decision": 0, "action": 0, "discussion": 0}
        all_keywords = []
        
        for seg in segments:
            text = seg.get("text", "").lower()
            speaker = seg.get("speaker", "unknown")
            
            for category, keywords in self.keyword_patterns.items():
                for keyword in keywords:
                    if keyword in text:
                        keyword_counts[category] += 1
                        all_keywords.append({"keyword": keyword, "category": category, "speaker": speaker})
        
        total_keywords = sum(keyword_counts.values())
        unique_keywords = len(set(kw["keyword"] for kw in all_keywords))
        
        # 키워드 다양성 점수
        keyword_diversity_score = unique_keywords / max(1, total_keywords)
        
        return KeywordMetric(
            total_keywords=total_keywords,
            unique_keywords=unique_keywords,
            keyword_diversity_score=round(keyword_diversity_score, 2),
            action_keywords_count=keyword_counts["action"],
            decision_keywords_count=keyword_counts["decision"]
        )
    
    def _analyze_sentiment(self, segments: List[Dict]) -> Optional[SentimentTrend]:
        """감정 분석 (간단한 구현)"""
        # 실제 구현에서는 NLP 라이브러리를 사용해야 함
        # 여기서는 간단한 키워드 기반 분석으로 대체
        
        positive_words = ["좋다", "excellent", "great", "있다", "있어요", "성공", "good"]
        negative_words = ["나쁘다", "bad", "어렵다", "difficult", "문제", "problem", "안된다"]
        
        sentiment_scores = []
        
        for seg in segments:
            text = seg.get("text", "").lower()
            positive_count = sum(1 for word in positive_words if word in text)
            negative_count = sum(1 for word in negative_words if word in text)
            
            segment_score = (positive_count - negative_count) / max(1, len(text.split()))
            sentiment_scores.append(segment_score)
        
        if not sentiment_scores:
            return None
        
        overall_sentiment = statistics.mean(sentiment_scores)
        sentiment_volatility = statistics.stdev(sentiment_scores) if len(sentiment_scores) > 1 else 0
        
        # 추이 판단
        first_half = sentiment_scores[:len(sentiment_scores)//2]
        second_half = sentiment_scores[len(sentiment_scores)//2:]
        
        first_avg = statistics.mean(first_half) if first_half else 0
        second_avg = statistics.mean(second_half) if second_half else 0
        
        if second_avg > first_avg + 0.1:
            trend = "improving"
        elif second_avg < first_avg - 0.1:
            trend = "declining"
        else:
            trend = "stable"
        
        return SentimentTrend(
            overall_sentiment_score=round(overall_sentiment, 2),
            sentiment_trend=trend,
            sentiment_volatility=round(sentiment_volatility, 2)
        )
    
    def _calculate_efficiency_score(
        self,
        participation_metrics: List[ParticipationMetric],
        decision_metric: DecisionMetric,
        action_item_metric: ActionItemMetric,
        time_distribution: TimeDistributionMetric,
        keyword_metric: KeywordMetric,
        sentiment_trend: Optional[SentimentTrend] = None
    ) -> EfficiencyMetrics:
        """종합 효율성 점수 계산"""
        
        # 참여도 균형 점수
        if participation_metrics:
            avg_participation_balance = statistics.mean([pm.participation_balance_score for pm in participation_metrics])
        else:
            avg_participation_balance = 0
        
        # 결정 효과성 점수
        decision_effectiveness = decision_metric.decision_clarity_score * min(1.0, decision_metric.decisions_per_hour / 5)
        
        # 액션 아이템 품질 점수
        action_item_quality = action_item_metric.action_item_clarity_score * min(1.0, action_item_metric.action_items_per_hour / 3)
        
        # 종합 점수 (가중 평균)
        overall_score = (
            avg_participation_balance * 0.25 +
            time_distribution.time_efficiency_score * 0.25 +
            decision_effectiveness * 0.25 +
            action_item_quality * 0.25
        )
        
        # 등급 계산
        if overall_score >= 0.9:
            grade = "A"
        elif overall_score >= 0.8:
            grade = "B"
        elif overall_score >= 0.7:
            grade = "C"
        elif overall_score >= 0.6:
            grade = "D"
        else:
            grade = "F"
        
        return EfficiencyMetrics(
            participation_balance=round(avg_participation_balance, 2),
            time_efficiency=round(time_distribution.time_efficiency_score, 2),
            decision_effectiveness=round(decision_effectiveness, 2),
            action_item_quality=round(action_item_quality, 2),
            overall_efficiency_score=round(overall_score, 2),
            efficiency_grade=grade,
            participation_metrics=participation_metrics,
            decision_metric=decision_metric,
            action_item_metric=action_item_metric,
            time_distribution=time_distribution,
            keyword_metric=keyword_metric,
            sentiment_trend=sentiment_trend
        )
    
    def _generate_recommendations(
        self,
        efficiency_metrics: EfficiencyMetrics,
        participation_metrics: List[ParticipationMetric],
        time_distribution: TimeDistributionMetric,
        analysis_depth: str
    ) -> EfficiencyRecommendations:
        """개선 제안 생성"""
        
        recommendations = {
            "participation": [],
            "time": [],
            "decision": [],
            "action_item": [],
            "general": []
        }
        
        # 참여도 개선 제안
        if efficiency_metrics.participation_balance < 0.7:
            unbalanced_speakers = [pm for pm in participation_metrics if pm.participation_balance_score < 0.5]
            if unbalanced_speakers:
                recommendations["participation"].append(Recommendation(
                    category="participation",
                    priority="high",
                    title="참여도 불균형 해소",
                    description="일부 참여자가 과도하게 발화하거나 부족한 문제를 개선하세요.",
                    specific_actions=[
                        f"'{pm.speaker_name}' 참여 시간 조정 (현재 {pm.speaking_percentage:.1f}%)",
                        "참여 균형을 위한 발화 기회 설정",
                        "패시브 참여자 적극 유도 방법 마련"
                    ],
                    expected_improvement="참여도 균형 점수 향상"
                ))
        
        # 시간 효율성 개선 제안
        if efficiency_metrics.time_efficiency < 0.8:
            recommendations["time"].append(Recommendation(
                category="time",
                priority="high" if time_distribution.silence_percentage > 30 else "medium",
                title="시간 효율성 개선",
                description=f"회의 시간 중 {time_distribution.silence_percentage:.1f}%가 무시간 상태입니다.",
                specific_actions=[
                    "의제별 시간 할당 및 관리",
                    "패시브 타임 최소화 전략 수립",
                    "회의 진행 역할 분담 (시간 관리자)"
                ],
                expected_improvement="시간 효율성 {efficiency_metrics.time_efficiency:.1f}% → 0.9+ 향상"
            ))
        
        # 결정 효과성 개선 제안
        if efficiency_metrics.decision_effectiveness < 0.7:
            recommendations["decision"].append(Recommendation(
                category="decision",
                priority="medium",
                title="결정 프로세스 개선",
                description="결정 효과성이 낮아 결정 지연 또는 모호성 문제가 있을 수 있습니다.",
                specific_actions=[
                    "미리 의제와 결정 포인트 공유",
                    "결정을 위한 시간 별도 배분",
                    "결정 기준 명확화 및 문서화"
                ],
                expected_improvement="결정 명확도 및 속도 향상"
            ))
        
        # 액션 아이템 개선 제안
        if efficiency_metrics.action_item_quality < 0.7:
            recommendations["action_item"].append(Recommendation(
                category="action_item",
                priority="high",
                title="액션 아이템 품질 개선",
                description="액션 아이템의 명확성이나 생성량이 부족합니다.",
                specific_actions=[
                    "SMART 원칙 적용 (Specific, Measurable, Achievable, Relevant, Time-bound)",
                    "액션 아이템 책임자 명시",
                    "정기적인 액션 아이템 리뷰 시스템"
                ],
                expected_improvement="액션 아이템 완료률 및 품질 향상"
            ))
        
        # 일반 제안
        if efficiency_metrics.overall_efficiency_score < 0.8:
            recommendations["general"].append(Recommendation(
                category="general",
                priority="medium",
                title="종합 회의 개선 방안",
                description=f"종합 효율성 점수 {efficiency_metrics.overall_efficiency_score:.1f}%로 개선이 필요합니다.",
                specific_actions=[
                    "회의 전 의제 공유 및 준비 요구",
                    "회의 중간 점검 루틴 도입",
                    "회의 후 피드백 및 개선점 반영"
                ],
                expected_improvement="종합 효율성 지속적 향상"
            ))
        
        # 빠른 개선책
        quick_wins = []
        if time_distribution.silence_percentage > 20:
            quick_wins.append("의도적인 패시브 타임 줄이기")
        if efficiency_metrics.participation_balance < 0.6:
            quick_wicks.append("라운딴식 발화 기회 제공")
        if efficiency_metrics.action_item_quality < 0.5:
            quick_wins.append("액션 아이템 템플릿 사용")
        
        return EfficiencyRecommendations(
            participation_recommendations=recommendations["participation"],
            time_recommendations=recommendations["time"],
            decision_recommendations=recommendations["decision"],
            action_item_recommendations=recommendations["action_item"],
            general_recommendations=recommendations["general"],
            total_recommendations=sum(len(recs) for recs in recommendations.values()),
            quick_wins=quick_wins
        )