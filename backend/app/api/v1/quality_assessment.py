"""
SPEC-QUALITY-001: 회의록 품질 평가 및 개선 제안 API
SPEC-QUALITY-MONITOR-001: 실시간 품질 점수/피드백/추세 분석 확장

엔드포인트:
- GET  /api/v1/quality/{task_id}                  - 기존 회의록 품질 평가
- POST /api/v1/quality/{task_id}/assess           - 새로운 품질 평가 요청
- GET  /api/v1/quality/{task_id}/improvements     - 개선 제안 조회
- GET  /api/v1/quality/{task_id}/quality-score    - 실시간 경량 점수 (AI 미사용)
- POST /api/v1/quality/{task_id}/quality-feedback - 사용자 품질 피드백 제출
- GET  /api/v1/quality/{task_id}/quality-feedback - 피드백 요약 조회
- GET  /api/v1/quality/{task_id}/quality-trends   - 품질 추세 분석
"""


from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select

from backend.app.errors import internal_server_error, not_found
from backend.app.exceptions import VoiceNoteError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db_session
from backend.db.models import TaskResult
from backend.schemas.quality import (
    LiveQualityScoreResponse,
    QualityAssessmentRequest,
    QualityAssessmentResponse,
    QualityFeedbackCreate,
    QualityFeedbackResponse,
    QualityFeedbackSummary,
    QualityImprovementResponse,
    QualityTrendsResponse,
)
from backend.services.quality_service import QualityService
from backend.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/quality", tags=["quality"])

# QualityService 인스턴스 (재사용)
_service = QualityService()


def _extract_minutes_text(result_data: dict | None) -> str:
    """TaskResult.result_data에서 회의록 본문 텍스트 추출."""
    if not result_data:
        return ""
    parts: list[str] = []
    for key in ("text", "markdown", "summary_text", "transcription"):
        value = result_data.get(key)
        if isinstance(value, str) and value.strip():
            parts.append(value)
    sections = result_data.get("sections")
    if isinstance(sections, dict):
        for value in sections.values():
            if isinstance(value, str) and value.strip():
                parts.append(value)
    segments = result_data.get("segments")
    if isinstance(segments, list):
        for seg in segments:
            if isinstance(seg, dict):
                t = seg.get("text")
                if isinstance(t, str) and t.strip():
                    parts.append(t)
    return "\n\n".join(parts)


def _extract_minutes_title(result_data: dict | None) -> str:
    if not result_data:
        return ""
    value = result_data.get("title")
    return value if isinstance(value, str) else ""


def _extract_minutes_content(task: TaskResult) -> tuple[str, str]:
    """TaskResult.result_data에서 품질 평가용 회의록 본문과 제목을 추출한다."""
    result_data = task.result_data or {}
    title = str(result_data.get("title") or result_data.get("meeting_title") or "")

    markdown = result_data.get("markdown")
    if isinstance(markdown, str) and markdown.strip():
        return markdown, title

    segments = result_data.get("segments")
    if isinstance(segments, list):
        segment_texts = [
            str(segment.get("text", ""))
            for segment in segments
            if isinstance(segment, dict) and segment.get("text")
        ]
        if segment_texts:
            return "\n".join(segment_texts), title

    summary_text = result_data.get("summary_text")
    if isinstance(summary_text, str) and summary_text.strip():
        return summary_text, title

    return "", title


@router.get(
    "/{task_id}",
    response_model=QualityAssessmentResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def get_quality_assessment(
    task_id: str,
    include_details: bool = Query(
        default=True,
        description="세부 평가 항목 포함 여부"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> QualityAssessmentResponse:
    """
    SPEC-QUALITY-001: 기존 회의록 품질 평가 조회

    저장된 회의록에 대해 품질 평가를 수행하고 결과를 반환합니다.
    """
    try:
        # TaskResult 조회 (회의록 결과)
        task_stmt = select(TaskResult).where(TaskResult.task_id == task_id)
        task = (await db.execute(task_stmt)).scalar_one_or_none()

        if not task:
            not_found(f"Task not found: {task_id}")

        content = _extract_minutes_text(task.result_data)
        if not content:
            not_found(f"Meeting minutes not found for task: {task_id}")

        # 품질 평가 수행
        assessment = await _service.assess_minutes(
            task_id=task_id,
            meeting_content=content,
            meeting_title=_extract_minutes_title(task.result_data),
            include_details=include_details,
            db=db,
        )

        return assessment

    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error(f"Quality assessment failed for task {task_id}", error=str(e))
        internal_server_error(f"품질 평가 중 오류가 발생했습니다: {str(e)}")


@router.post(
    "/{task_id}/assess",
    response_model=QualityAssessmentResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def request_quality_assessment(
    task_id: str,
    payload: QualityAssessmentRequest,
    db: AsyncSession = Depends(get_db_session),
) -> QualityAssessmentResponse:
    """
    SPEC-QUALITY-002: 새로운 품질 평가 요청

    지정된 회의록에 대해 새로운 품질 평가를 수행합니다.
    평가 기준을 커스터마이징할 수 있습니다.
    """
    try:
        task_stmt = select(TaskResult).where(TaskResult.task_id == task_id)
        task = (await db.execute(task_stmt)).scalar_one_or_none()

        if not task:
            not_found(f"Task not found: {task_id}")

        content = _extract_minutes_text(task.result_data)
        if not content:
            not_found(f"Meeting minutes not found for task: {task_id}")

        assessment = await _service.assess_minutes(
            task_id=task_id,
            meeting_content=content,
            meeting_title=_extract_minutes_title(task.result_data),
            custom_criteria=payload.criteria,
            assessment_focus=payload.assessment_focus,
            db=db,
        )

        return assessment

    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error(f"Custom quality assessment failed for task {task_id}", error=str(e))
        internal_server_error(f"품질 평가 중 오류가 발생했습니다: {str(e)}")


@router.get(
    "/{task_id}/improvements",
    response_model=QualityImprovementResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def get_improvement_suggestions(
    task_id: str,
    improvement_type: str | None = Query(
        default="all",
        description="개선 제안 유형 (structure, content, clarity, completeness, all)"
    ),
    priority: str | None = Query(
        default="high",
        description="우선순위 (high, medium, low)"
    ),
    db: AsyncSession = Depends(get_db_session),
) -> QualityImprovementResponse:
    """
    SPEC-QUALITY-003: 개선 제안 조회

    회의록 개선을 위한 구체적인 제안을 제공합니다.
    """
    try:
        task_stmt = select(TaskResult).where(TaskResult.task_id == task_id)
        task = (await db.execute(task_stmt)).scalar_one_or_none()

        if not task:
            not_found(f"Task not found: {task_id}")

        # 개선 제안 가져오기
        improvements = await _service.get_improvement_suggestions(
            task_id=task_id,
            improvement_type=improvement_type,
            priority=priority,
            db=db
        )

        return QualityImprovementResponse(
            task_id=task_id,
            improvements=improvements,
            suggested_actions=await _service.generate_action_plan(improvements),
            total_improvements=len(improvements)
        )

    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error(f"Improvement suggestions failed for task {task_id}", error=str(e))
        internal_server_error(f"개선 제안 생성 중 오류가 발생했습니다: {str(e)}")


@router.get("/health")
async def health_check() -> dict[str, str]:
    """품질 평가 시스템 상태 확인"""
    return {
        "status": "healthy",
        "service": "quality_assessment",
        "version": "1.0.0"
    }


# ---------------------------------------------------------------------------
# SPEC-QUALITY-MONITOR-001: 실시간 모니터링 엔드포인트
# ---------------------------------------------------------------------------


async def _load_minutes_text_or_404(db: AsyncSession, task_id: str) -> str:
    """TaskResult.result_data에서 회의록 본문을 추출하거나 404."""
    task_stmt = select(TaskResult).where(TaskResult.task_id == task_id)
    task = (await db.execute(task_stmt)).scalar_one_or_none()
    if task is None:
        not_found(f"Task not found: {task_id}")
    content = _extract_minutes_text(task.result_data)
    if not content:
        not_found(f"Meeting minutes not found for task: {task_id}")
    return content


@router.get(
    "/{task_id}/quality-score",
    response_model=LiveQualityScoreResponse,
    responses={404: {"description": "회의 데이터 없음"}},
)
async def get_live_quality_score(
    task_id: str,
    persist: bool = Query(
        default=True,
        description="True면 점수 스냅샷을 저장해 추세 분석에 활용",
    ),
    db: AsyncSession = Depends(get_db_session),
) -> LiveQualityScoreResponse:
    """REQ-QM-003: AI 호출 없는 경량 실시간 품질 점수.

    저장된 회의록 본문에 대해 기본 분석만으로 빠르게 점수를 계산합니다.
    `persist=true`일 때 스냅샷이 저장되어 `/quality-trends`에서 활용됩니다.
    """
    content = await _load_minutes_text_or_404(db, task_id)

    try:
        return await _service.compute_live_score(
            task_id=task_id,
            meeting_content=content,
            db=db,
            persist_snapshot=persist,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error("실시간 품질 점수 계산 실패", task_id=task_id, error=str(e))
        internal_server_error(f"실시간 품질 점수 계산 실패: {e}")


@router.post(
    "/{task_id}/quality-feedback",
    response_model=QualityFeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Task 없음"}},
)
async def submit_quality_feedback(
    task_id: str,
    payload: QualityFeedbackCreate,
    db: AsyncSession = Depends(get_db_session),
) -> QualityFeedbackResponse:
    """REQ-QM-001: 사용자 피드백 제출 (1~5 별점 + 카테고리 + 코멘트)."""
    task = (
        await db.execute(select(TaskResult).where(TaskResult.task_id == task_id))
    ).scalar_one_or_none()
    if task is None:
        not_found(f"Task not found: {task_id}")

    try:
        return await _service.submit_feedback(
            db=db,
            task_id=task_id,
            user_id=None,
            payload=payload,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error("품질 피드백 저장 실패", task_id=task_id, error=str(e))
        internal_server_error(f"품질 피드백 저장 실패: {e}")


@router.get(
    "/{task_id}/quality-feedback",
    response_model=QualityFeedbackSummary,
)
async def list_quality_feedback(
    task_id: str,
    recent_limit: int = Query(default=10, ge=1, le=50),
    db: AsyncSession = Depends(get_db_session),
) -> QualityFeedbackSummary:
    """REQ-QM-001: 누적된 피드백 요약 (평균 별점, 카테고리 분포, 최근 N건)."""
    try:
        return await _service.get_feedback_summary(
            db=db,
            task_id=task_id,
            recent_limit=recent_limit,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error("피드백 요약 조회 실패", task_id=task_id, error=str(e))
        internal_server_error(f"피드백 요약 조회 실패: {e}")


@router.get(
    "/{task_id}/quality-trends",
    response_model=QualityTrendsResponse,
)
async def get_quality_trends(
    task_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    warning_drop_threshold: float | None = Query(
        default=None,
        ge=0.0,
        le=100.0,
        description="이 점수 이상 하락 시 경고 메시지를 포함",
    ),
    db: AsyncSession = Depends(get_db_session),
) -> QualityTrendsResponse:
    """REQ-QM-002: 저장된 스냅샷 기반 품질 추세 분석.

    `quality-score` 호출 시마다 누적되는 스냅샷을 기반으로
    평균/최저/최고/방향(up|down|stable) 및 하락 경고를 제공합니다.
    """
    try:
        return await _service.get_quality_trends(
            db=db,
            task_id=task_id,
            limit=limit,
            warning_drop_threshold=warning_drop_threshold,
        )
    except VoiceNoteError:
        raise
    except Exception as e:
        logger.error("품질 추세 분석 실패", task_id=task_id, error=str(e))
        internal_server_error(f"품질 추세 분석 실패: {e}")
