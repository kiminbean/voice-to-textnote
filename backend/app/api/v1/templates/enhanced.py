"""
Enhanced Template System - Template-based Meeting Minutes Generation
REQ-TMPL-002: GET /api/v1/templates/types - 템플릿 유형 목록
REQ-TMPL-004: POST /api/v1/templates/generate - 템플릿 기반 회의록 생성
REQ-TMPL-005: GET /api/v1/templates/predefined - 미리 정의된 템플릿 조회
"""

import json
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from backend.app.dependencies import get_db_session, get_redis_client
from backend.app.errors import not_found, unprocessable
from backend.db.models import TaskResult
from backend.schemas.template import TemplateDetail
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/templates", tags=["templates"])


class MeetingType(str, Enum):
    """회의 유형 정의"""
    GENERAL = "general"  # 일반 회의
    ONE_ON_ONE = "one_on_one"  # 1:1 미팅
    BRAINSTORMING = "brainstorming"  # 브레인스토밍
    PROJECT = "project"  # 프로젝트 리뷰
    KICKOFF = "kickoff"  # 프로젝트 킥오프
    RETROSPECTIVE = "retrospective"  # 회고
    DECISION = "decision"  # 의사결정 회의


class TemplateSection(BaseModel):
    """템플릿 섹션 정의"""
    title: str
    required: bool = True
    order: int
    placeholder: Optional[str] = None
    subsections: List["TemplateSection"] = Field(default_factory=list)


class PredefinedTemplate(BaseModel):
    """미리 정의된 템플릿"""
    template_id: str
    name: str
    meeting_type: MeetingType
    description: str
    sections: List[TemplateSection]
    default_config: Dict[str, Any] = Field(default_factory=dict)


class TemplateGenerationRequest(BaseModel):
    """템플릿 기반 회의록 생성 요청"""
    minutes_task_id: str  # 원본 회의록 태스크 ID
    template_id: str  # 사용할 템플릿 ID
    custom_sections: Optional[Dict[str, Any]] = None
    include_summary: bool = True
    include_action_items: bool = True
    include_participants: bool = True


# 미리 정의된 템플릿 정의
PREDEFINED_TEMPLATES: Dict[MeetingType, PredefinedTemplate] = {
    MeetingType.GENERAL: PredefinedTemplate(
        template_id="general-meeting",
        name="일반 회의록",
        meeting_type=MeetingType.GENERAL,
        description="표준 일반 회의용 템플릿",
        sections=[
            TemplateSection(
                title="회의 개요",
                required=True,
                order=1,
                placeholder="회의 목적 및 일정",
            ),
            TemplateSection(
                title="참석자",
                required=True,
                order=2,
            ),
            TemplateSection(
                title="안건별 논의 내용",
                required=True,
                order=3,
                subsections=[
                    TemplateSection(title="안건 1", order=3.1),
                    TemplateSection(title="안건 2", order=3.2),
                ],
            ),
            TemplateSection(
                title="결정 사항",
                required=True,
                order=4,
            ),
            TemplateSection(
                title="할당된 업무",
                required=True,
                order=5,
            ),
            TemplateSection(
                title="다음 회의",
                required=False,
                order=6,
                placeholder="다次会议일 및 안건",
            ),
        ],
        default_config={
            "section_separator": "---",
            "item_prefix": "- ",
            "bold_key_points": True,
        },
    ),
    MeetingType.ONE_ON_ONE: PredefinedTemplate(
        template_id="one-on-one",
        name="1:1 미팅록",
        meeting_type=MeetingType.ONE_ON_ONE,
        description="매니저와 팀원 간 1:1 미팅용 템플릿",
        sections=[
            TemplateSection(
                title="회의 개요",
                required=True,
                order=1,
                placeholder="회의 목적과 주요 화제",
            ),
            TemplateSection(
                title="팀원 업무 업데이트",
                required=True,
                order=2,
            ),
            TemplateSection(
                title="현재 과제 및 도움 필요사항",
                required=True,
                order=3,
            ),
            TemplateSection(
                title="피드백 및 성과",
                required=True,
                order=4,
            ),
            TemplateSection(
                title="개발 목표 및 기대치",
                required=True,
                order=5,
            ),
            TemplateSection(
                title="관심사 및 건의사항",
                required=False,
                order=6,
            ),
        ],
        default_config={
            "focus_on_employee": True,
            "include_growth_area": True,
            "feedback_format": "structured",
        },
    ),
    MeetingType.BRAINSTORMING: PredefinedTemplate(
        template_id="brainstorming",
        name="아이디어 브레인스토밍",
        meeting_type=MeetingType.BRAINSTORMING,
        description="아이디어 생성 및 발산적 사고용 템플릿",
        sections=[
            TemplateSection(
                title="문제 정의",
                required=True,
                order=1,
                placeholder="해결하려는 문제 또기회",
            ),
            TemplateSection(
                title="참석자 및 역할",
                required=True,
                order=2,
            ),
            TemplateSection(
                title="아이디어 생성",
                required=True,
                order=3,
                subsections=[
                    TemplateSection(title="아이디어 1", order=3.1),
                    TemplateSection(title="아이디어 2", order=3.2),
                ],
            ),
            TemplateSection(
                title="아이디어 평가",
                required=True,
                order=4,
            ),
            TemplateSection(
                title="우선순위 결정",
                required=True,
                order=5,
            ),
            TemplateSection(
                title="실행 계획",
                required=False,
                order=6,
                placeholder="다음 단계 및 담당자",
            ),
        ],
        default_config={
            "ideation_method": "brainwriting",
            "evaluation_criteria": ["feasibility", "impact", "urgency"],
            "prioritization_matrix": True,
        },
    ),
    MeetingType.PROJECT: PredefinedTemplate(
        template_id="project-review",
        name="프로젝트 리뷰",
        meeting_type=MeetingType.PROJECT,
        description="프로젝트 진행 상황 검토용 템플릿",
        sections=[
            TemplateSection(
                title="프로젝트 개요",
                required=True,
                order=1,
                placeholder="프로젝트 목표 및 현재 단계",
            ),
            TemplateSection(
                title="진행 상황",
                required=True,
                order=2,
            ),
            TemplateSection(
                title="성과 및 달성 사항",
                required=True,
                order=3,
            ),
            TemplateSection(
                title="문제 및 장애물",
                required=True,
                order=4,
            ),
            TemplateSection(
                title="리스크 관리",
                required=True,
                order=5,
            ),
            TemplateSection(
                title="다음 단계 계획",
                required=True,
                order=6,
            ),
        ],
        default_config={
            "include_metrics": True,
            "risk_assessment": True,
            "milestone_tracking": True,
        },
    ),
    MeetingType.RETROSPECTIVE: PredefinedTemplate(
        template_id="retrospective",
        name="회고 회의록",
        meeting_type=MeetingType.RETROSPECTIVE,
        description="스프린트 또는 프로젝트 종료 후 회고용 템플릿",
        sections=[
            TemplateSection(
                title="회고 대상 및 기간",
                required=True,
                order=1,
                placeholder="회고할 프로젝트/스프린트 정보",
            ),
            TemplateSection(
                title="성공했던 점",
                required=True,
                order=2,
            ),
            TemplateSection(
                title="개선할 점",
                required=True,
                order=3,
            ),
            TemplateSection(
                title="앞으로 시도해볼 점",
                required=True,
                order=4,
            ),
            TemplateSection(
                title="교훈 및 배움",
                required=False,
                order=5,
            ),
            TemplateSection(
                title="행동 계획",
                required=True,
                order=6,
            ),
        ],
        default_config={
            "retrospective_format": "start_stop_continue",
            "actionable_insights": True,
            "team_learning_focus": True,
        },
    ),
}


@router.get("/types", response_model=List[PredefinedTemplate])
async def get_template_types() -> List[PredefinedTemplate]:
    """지원하는 템플릿 유형 목록 조회"""
    return list(PREDEFINED_TEMPLATES.values())


@router.get("/predefined", response_model=List[PredefinedTemplate])
async def get_predefined_templates(
    meeting_type: Optional[MeetingType] = Query(
        default=None,
        description="특정 회의 유형의 템플릿만 필터링",
    ),
) -> List[PredefinedTemplate]:
    """미리 정의된 템플릿 목록 조회"""
    templates = list(PREDEFINED_TEMPLATES.values())
    
    if meeting_type:
        templates = [t for t in templates if t.meeting_type == meeting_type]
    
    return templates


async def _get_minutes_data(redis_client: aioredis.Redis, db_session, task_id: str) -> dict:
    """Redis 우선, DB 폴백으로 회의록 데이터 조회"""
    # Redis 조회
    redis_key = f"task:min:result:{task_id}"
    raw = await redis_client.get(redis_key)
    if raw:
        return json.loads(raw)

    # DB 폴백
    from sqlalchemy import select
    
    stmt = select(TaskResult).where(
        TaskResult.task_id == task_id,
        TaskResult.task_type == "minutes",
        TaskResult.status == "completed",
    )
    result = await db_session.execute(stmt)
    record = result.scalars().first()

    if record and record.result_data:
        return record.result_data

    raise not_found(f"회의록 데이터를 찾을 수 없습니다: {task_id}")


def _apply_template_to_minutes(
    minutes_data: dict,
    template: PredefinedTemplate,
    custom_sections: Optional[Dict[str, Any]] = None
) -> dict:
    """템플릿을 회의록 데이터에 적용"""
    template_config = template.default_config.copy()
    if custom_sections:
        template_config.update(custom_sections)

    # 템플릿 기반 구조화된 회의록 생성
    structured_minutes = {
        "template_info": {
            "template_id": template.template_id,
            "template_name": template.name,
            "meeting_type": template.meeting_type,
            "applied_at": datetime.now(UTC).isoformat(),
        },
        "metadata": {
            "title": f"{template.name} - {minutes_data.get('meeting_title', '회의록')}",
            "created_at": minutes_data.get("created_at", datetime.now(UTC).isoformat()),
        },
        "sections": {},
    }

    # segments 데이터에서 발화 내용 구조화
    segments = minutes_data.get("segments", [])
    
    # 섹션별 데이터 분배 로직 (간소화된 버전)
    for section in template.sections:
        section_key = section.title.lower().replace(" ", "_")
        structured_minutes["sections"][section_key] = {
            "title": section.title,
            "required": section.required,
            "content": [],
            "subsections": {},
        }

        # 실제 구현에서는 segments 내용을 섹션별로 분류
        # 여기서는 예시 데이터로 채움
        if section_key == "참석자":
            participants = list(set(seg.get("speaker", "알 수 없음") for seg in segments))
            structured_minutes["sections"][section_key]["content"] = participants
        
        elif section_key == "회의_개요":
            structured_minutes["sections"][section_key]["content"] = [
                "회의 목적에 대한 내용을 여기에 작성합니다."
            ]
        
        # 다른 섹션들에 대한 분류 로직 추가...

    # 요약 및 액션 항목 추가
    if template_config.get("include_summary", True):
        summary_data = minutes_data.get("summary", {})
        if summary_data:
            structured_minutes["summary"] = summary_data

    if template_config.get("include_action_items", True):
        action_items = minutes_data.get("action_items", [])
        if action_items:
            structured_minutes["action_items"] = action_items

    return structured_minutes


@router.post("/generate", response_model=dict)
async def generate_template_based_minutes(
    request: TemplateGenerationRequest,
    redis_client: aioredis.Redis = Depends(get_redis_client),
    db_session = Depends(get_db_session),
) -> dict:
    """템플릿 기반 회의록 생성"""
    
    # 원본 회의록 데이터 조회
    minutes_data = await _get_minutes_data(redis_client, db_session, request.minutes_task_id)
    
    # 템플릿 확인
    if request.template_id not in PREDEFINED_TEMPLATES:
        available_templates = list(PREDEFINED_TEMPLATES.keys())
        unprocessable(
            f"지원하지 않는 템플릿입니다. 사용 가능한 템플릿: {available_templates}"
        )
    
    template = PREDEFINED_TEMPLATES[MeetingType(request.template_id)]
    
    # 템플릿 적용
    structured_minutes = _apply_template_to_minutes(
        minutes_data,
        template,
        request.custom_sections
    )
    
    # 결과 캐싱
    task_id = f"template_{request.template_id}_{request.minutes_task_id}"
    result_key = f"task:template:result:{task_id}"
    
    await redis_client.setex(
        result_key,
        86400,  # 24시간 TTL
        json.dumps(structured_minutes, ensure_ascii=False)
    )
    
    logger.info(
        "템플릿 기반 회의록 생성 완료",
        template_id=request.template_id,
        original_task_id=request.minutes_task_id,
        task_id=task_id,
    )
    
    return {
        "task_id": task_id,
        "template_id": request.template_id,
        "template_name": template.name,
        "status": "completed",
        "structured_data": structured_minutes,
    }