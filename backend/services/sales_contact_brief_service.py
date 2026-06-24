"""Sales contact brief generation service."""

from __future__ import annotations

import json
import uuid
from csv import DictWriter
from datetime import UTC, datetime
from io import StringIO
from typing import Any, cast

import redis.asyncio as aioredis
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import settings
from backend.db.auth_models import MeetingOwnership
from backend.db.models import TaskResult
from backend.db.search_models import ensure_search_index_table, index_search_entry
from backend.ml.openai_client import structured_json_completion_options
from backend.schemas.sales_contact_brief import (
    SalesContactBriefResponse,
    SalesContactCrmUpdateRequest,
    SalesContactDeal,
    SalesContactIdentity,
    SalesContactListItem,
    SalesContactListResponse,
    SalesNextStep,
)
from backend.schemas.study_pack import StudySourceRef
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_SALES_CONTACT_BRIEF_KEY_PREFIX = "sales_contact_brief:"
_SALES_CONTACT_BRIEF_RESULT_PREFIX = "sales-contact-brief:"
_MINUTES_KEY_PREFIX = "task:min:result:"


def _sales_contact_brief_cache_key(task_id: str) -> str:
    return f"{_SALES_CONTACT_BRIEF_KEY_PREFIX}{task_id}"


def _sales_contact_brief_result_task_id(task_id: str) -> str:
    return f"{_SALES_CONTACT_BRIEF_RESULT_PREFIX}{task_id}"


def _parse_created_at(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _sales_contact_item_text(item: SalesContactListItem) -> str:
    parts = [
        item.contact.name,
        item.contact.company,
        item.contact.role,
        item.contact.email,
        item.contact.phone,
        item.deal.stage,
        item.deal.value_hint,
        item.deal.urgency,
        item.crm_status,
        item.crm_note,
        item.follow_up_message,
        *item.customer_needs,
        *item.pain_points,
        *(step.task for step in item.next_steps),
        *(step.owner for step in item.next_steps if step.owner),
        *(step.due for step in item.next_steps if step.due),
    ]
    return " ".join(str(part) for part in parts if part).casefold()


class SalesContactBriefSourceNotFoundError(ValueError):
    """Raised when source minutes or cached contact brief content is missing."""


class SalesContactBriefValidationError(ValueError):
    """Raised when generated contact brief content cannot be validated."""


class SalesContactBriefService:
    """Generate customer/contact follow-up artifacts from completed minutes results."""

    def _get_client(self) -> OpenAI:
        return OpenAI(api_key=settings.llm_api_key, base_url=settings.llm_base_url)

    async def get(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
    ) -> SalesContactBriefResponse:
        """Load a cached sales contact brief."""
        raw = await redis_client.get(_sales_contact_brief_cache_key(task_id))
        if raw is None:
            raise SalesContactBriefSourceNotFoundError("영업 연락처 브리프를 찾을 수 없습니다.")
        return SalesContactBriefResponse.model_validate_json(cast(str | bytes | bytearray, raw))

    async def generate(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
        *,
        language: str = "ko",
        max_tokens: int = 1200,
        force_refresh: bool = False,
        db_session: AsyncSession | None = None,
        owner_id: str | uuid.UUID | None = None,
        guest_session_id: str | None = None,
    ) -> SalesContactBriefResponse:
        """Generate or return a cached sales contact brief for a minutes task."""
        cache_key = _sales_contact_brief_cache_key(task_id)
        if not force_refresh:
            cached = await redis_client.get(cache_key)
            if cached is not None:
                result = SalesContactBriefResponse.model_validate_json(
                    cast(str | bytes | bytearray, cached)
                )
                if db_session is not None:
                    await self._persist_brief(
                        task_id,
                        result,
                        db_session,
                        owner_id=owner_id,
                        guest_session_id=guest_session_id,
                    )
                    await self._index_brief(task_id, result, db_session)
                return result

        minutes_data = await self._load_minutes(
            task_id,
            redis_client,
            db_session=db_session,
        )
        transcript = self._format_transcript(minutes_data)
        if not transcript.strip():
            raise SalesContactBriefSourceNotFoundError("회의록 내용이 비어 있습니다.")

        source_refs = self._extract_source_refs(minutes_data)
        prompt = self._build_prompt(transcript, language=language)
        client = self._get_client()
        logger.info("Sales contact brief API 호출", task_id=task_id)
        response = client.chat.completions.create(
            model=settings.summary_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **structured_json_completion_options(settings.summary_model, settings.llm_base_url),
        )
        response_text = response.choices[0].message.content or ""
        try:
            payload = self._parse_response(response_text)
            result = SalesContactBriefResponse(
                task_id=task_id,
                contact=SalesContactIdentity.model_validate(payload.get("contact") or {}),
                deal=SalesContactDeal.model_validate(payload.get("deal") or {}),
                customer_needs=[
                    str(item).strip()
                    for item in payload.get("customer_needs", [])
                    if str(item).strip()
                ],
                pain_points=[
                    str(item).strip()
                    for item in payload.get("pain_points", [])
                    if str(item).strip()
                ],
                objections=[
                    str(item).strip()
                    for item in payload.get("objections", [])
                    if str(item).strip()
                ],
                next_steps=[
                    SalesNextStep.model_validate(item)
                    for item in payload.get("next_steps", [])
                    if isinstance(item, dict)
                ],
                follow_up_message=str(payload.get("follow_up_message", "")).strip(),
                source_refs=source_refs,
                created_at=datetime.now(UTC).isoformat(),
            )
            self._validate_result(result)
        except Exception as exc:
            logger.warning(
                "Sales contact brief AI 응답 파싱 실패, 회의록 기반 기본 브리프로 폴백",
                task_id=task_id,
                error=str(exc),
            )
            result = self._build_fallback_result(task_id, minutes_data, source_refs)
        await redis_client.set(
            cache_key,
            result.model_dump_json(),
            ex=settings.summary_result_ttl,
        )
        if db_session is not None:
            await self._persist_brief(
                task_id,
                result,
                db_session,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
            )
            await self._index_brief(task_id, result, db_session)
        return result

    async def list_contacts(
        self,
        db_session: AsyncSession,
        *,
        page: int = 1,
        page_size: int = 20,
        query: str | None = None,
        owner_id: uuid.UUID | None = None,
        guest_session_id: str | None = None,
    ) -> SalesContactListResponse:
        """Return persisted sales/contact brief artifacts as a CRM-style list."""
        stmt = (
            select(TaskResult)
            .where(
                TaskResult.task_type == "sales_contact_brief",
                TaskResult.status == "completed",
            )
            .order_by(TaskResult.completed_at.desc(), TaskResult.created_at.desc())
        )
        if owner_id is not None:
            stmt = stmt.join(MeetingOwnership, MeetingOwnership.task_id == TaskResult.task_id)
            stmt = stmt.where(
                MeetingOwnership.owner_id == owner_id,
                MeetingOwnership.team_id.is_(None),
            )
        elif guest_session_id is not None:
            stmt = stmt.where(
                TaskResult.is_guest.is_(True),
                TaskResult.guest_session_id == guest_session_id,
            )
        result = await db_session.execute(stmt)
        records = list(result.scalars().all())
        items = [self._record_to_list_item(record) for record in records]

        query_text = (query or "").strip().casefold()
        if query_text:
            items = [item for item in items if query_text in _sales_contact_item_text(item)]

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        return SalesContactListResponse(
            items=items[start:end],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def export_contacts_csv(
        self,
        db_session: AsyncSession,
        *,
        query: str | None = None,
        owner_id: uuid.UUID | None = None,
        guest_session_id: str | None = None,
    ) -> str:
        """Export all matching sales contacts as CRM-importable CSV."""
        response = await self.list_contacts(
            db_session,
            page=1,
            page_size=10_000,
            query=query,
            owner_id=owner_id,
            guest_session_id=guest_session_id,
        )
        fieldnames = [
            "name",
            "company",
            "role",
            "email",
            "phone",
            "deal_stage",
            "deal_value_hint",
            "urgency",
            "customer_needs",
            "pain_points",
            "next_steps",
            "follow_up_message",
            "crm_status",
            "crm_note",
            "source_task_id",
            "artifact_task_id",
            "created_at",
            "crm_updated_at",
        ]
        output = StringIO()
        writer = DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for item in response.items:
            writer.writerow(
                {
                    "name": item.contact.name or "",
                    "company": item.contact.company or "",
                    "role": item.contact.role or "",
                    "email": item.contact.email or "",
                    "phone": item.contact.phone or "",
                    "deal_stage": item.deal.stage,
                    "deal_value_hint": item.deal.value_hint or "",
                    "urgency": item.deal.urgency,
                    "customer_needs": "; ".join(item.customer_needs),
                    "pain_points": "; ".join(item.pain_points),
                    "next_steps": "; ".join(
                        self._format_export_next_step(step) for step in item.next_steps
                    ),
                    "follow_up_message": item.follow_up_message,
                    "crm_status": item.crm_status,
                    "crm_note": item.crm_note,
                    "source_task_id": item.source_task_id,
                    "artifact_task_id": item.artifact_task_id,
                    "created_at": item.created_at,
                    "crm_updated_at": item.crm_updated_at or "",
                }
            )
        return output.getvalue()

    async def update_crm(
        self,
        db_session: AsyncSession,
        artifact_task_id: str,
        request: SalesContactCrmUpdateRequest,
        *,
        owner_id: uuid.UUID | None = None,
        guest_session_id: str | None = None,
    ) -> SalesContactListItem:
        """Persist editable CRM status/note metadata on a sales contact artifact."""
        stmt = select(TaskResult).where(
            TaskResult.task_id == artifact_task_id,
            TaskResult.task_type == "sales_contact_brief",
            TaskResult.status == "completed",
        )
        if owner_id is not None:
            stmt = stmt.join(MeetingOwnership, MeetingOwnership.task_id == TaskResult.task_id)
            stmt = stmt.where(
                MeetingOwnership.owner_id == owner_id,
                MeetingOwnership.team_id.is_(None),
            )
        elif guest_session_id is not None:
            stmt = stmt.where(
                TaskResult.is_guest.is_(True),
                TaskResult.guest_session_id == guest_session_id,
            )
        query_result = await db_session.execute(stmt)
        record = query_result.scalar_one_or_none()
        if record is None:
            raise SalesContactBriefSourceNotFoundError("영업 연락처를 찾을 수 없습니다.")

        result_data = dict(record.result_data or {})
        crm = {
            "status": request.status.strip() or "open",
            "note": request.note.strip(),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        result_data["crm"] = crm
        record.result_data = result_data
        await db_session.commit()
        return self._record_to_list_item(record)

    async def _persist_brief(
        self,
        task_id: str,
        result: SalesContactBriefResponse,
        db_session: AsyncSession,
        owner_id: str | uuid.UUID | None = None,
        guest_session_id: str | None = None,
    ) -> None:
        """Best-effort persistence for the customer/contact list surface."""
        artifact_task_id = _sales_contact_brief_result_task_id(task_id)
        completed_at = _parse_created_at(result.created_at) or datetime.now(UTC).replace(
            tzinfo=None
        )
        try:
            stmt = select(TaskResult).where(TaskResult.task_id == artifact_task_id)
            query_result = await db_session.execute(stmt)
            record = query_result.scalar_one_or_none()
            if record is None:
                record = TaskResult(task_id=artifact_task_id)
                db_session.add(record)

            record.task_type = "sales_contact_brief"
            record.status = "completed"
            record.result_data = result.model_dump(mode="json")
            record.input_metadata = {
                "source_task_id": task_id,
                "artifact_type": "sales_contact_brief",
            }
            record.error_message = None
            record.completed_at = completed_at.replace(tzinfo=None)
            await self._inherit_access(
                db_session,
                source_task_id=task_id,
                artifact_task_id=artifact_task_id,
                record=record,
                owner_id=owner_id,
                guest_session_id=guest_session_id,
            )
            await db_session.commit()
        except Exception as exc:
            await db_session.rollback()
            logger.warning(
                "Sales contact brief persistence failed",
                task_id=task_id,
                error=str(exc),
            )

    async def _inherit_access(
        self,
        db_session: AsyncSession,
        *,
        source_task_id: str,
        artifact_task_id: str,
        record: TaskResult,
        owner_id: str | uuid.UUID | None,
        guest_session_id: str | None,
    ) -> None:
        explicit_owner_id = self._coerce_owner_id(owner_id)
        if explicit_owner_id is not None:
            await self._ensure_ownership(
                db_session,
                artifact_task_id=artifact_task_id,
                owner_id=explicit_owner_id,
                team_id=None,
            )

        source_record_result = await db_session.execute(
            select(TaskResult).where(TaskResult.task_id == source_task_id)
        )
        source_record = source_record_result.scalar_one_or_none()
        inherited_guest_session_id = guest_session_id
        if source_record is not None and source_record.is_guest:
            inherited_guest_session_id = inherited_guest_session_id or source_record.guest_session_id
        if inherited_guest_session_id:
            record.is_guest = True
            record.guest_session_id = inherited_guest_session_id

        source_ownership_result = await db_session.execute(
            select(MeetingOwnership).where(MeetingOwnership.task_id == source_task_id)
        )
        for source_ownership in source_ownership_result.scalars().all():
            await self._ensure_ownership(
                db_session,
                artifact_task_id=artifact_task_id,
                owner_id=source_ownership.owner_id,
                team_id=source_ownership.team_id,
            )

    async def _ensure_ownership(
        self,
        db_session: AsyncSession,
        *,
        artifact_task_id: str,
        owner_id: uuid.UUID,
        team_id: uuid.UUID | None,
    ) -> None:
        existing_result = await db_session.execute(
            select(MeetingOwnership).where(
                MeetingOwnership.task_id == artifact_task_id,
                MeetingOwnership.owner_id == owner_id,
                MeetingOwnership.team_id == team_id
                if team_id is not None
                else MeetingOwnership.team_id.is_(None),
            )
        )
        if existing_result.scalar_one_or_none() is not None:
            return

        db_session.add(
            MeetingOwnership(
                task_id=artifact_task_id,
                owner_id=owner_id,
                team_id=team_id,
                shared_at=datetime.now(UTC).replace(tzinfo=None) if team_id else None,
            )
        )

    def _coerce_owner_id(self, owner_id: str | uuid.UUID | None) -> uuid.UUID | None:
        if owner_id is None:
            return None
        if isinstance(owner_id, uuid.UUID):
            return owner_id
        try:
            return uuid.UUID(str(owner_id))
        except ValueError:
            return None

    def _record_to_list_item(self, record: TaskResult) -> SalesContactListItem:
        data = SalesContactBriefResponse.model_validate(record.result_data or {})
        metadata = record.input_metadata or {}
        source_task_id = str(metadata.get("source_task_id") or data.task_id)
        completed_at = record.completed_at.isoformat() if record.completed_at else None
        crm = record.result_data.get("crm") if isinstance(record.result_data, dict) else {}
        if not isinstance(crm, dict):
            crm = {}
        return SalesContactListItem(
            artifact_task_id=record.task_id,
            source_task_id=source_task_id,
            contact=data.contact,
            deal=data.deal,
            customer_needs=data.customer_needs,
            pain_points=data.pain_points,
            next_steps=data.next_steps,
            follow_up_message=data.follow_up_message,
            crm_status=str(crm.get("status") or "open"),
            crm_note=str(crm.get("note") or ""),
            crm_updated_at=crm.get("updated_at")
            if isinstance(crm.get("updated_at"), str)
            else None,
            created_at=data.created_at,
            completed_at=completed_at,
        )

    def _format_export_next_step(self, step: SalesNextStep) -> str:
        details = [step.task]
        if step.owner:
            details.append(f"owner={step.owner}")
        if step.due:
            details.append(f"due={step.due}")
        return " | ".join(details)

    async def _index_brief(
        self,
        task_id: str,
        result: SalesContactBriefResponse,
        db_session: AsyncSession,
    ) -> None:
        """Best-effort FTS indexing for generated sales/customer follow-up briefs."""
        result_data = result.model_dump(mode="json")
        created_at = _parse_created_at(result.created_at)

        try:
            await db_session.run_sync(
                lambda sync_session: ensure_search_index_table(sync_session.connection())
            )
            await db_session.run_sync(
                lambda sync_session: index_search_entry(
                    sync_session,
                    task_id=task_id,
                    task_type="sales_contact_brief",
                    result_data=result_data,
                    created_at=created_at,
                )
            )
            await db_session.commit()
        except Exception as exc:
            await db_session.rollback()
            logger.warning(
                "Sales contact brief search index update failed",
                task_id=task_id,
                error=str(exc),
            )

    async def _load_minutes(
        self,
        task_id: str,
        redis_client: aioredis.Redis,
        *,
        db_session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        raw = await redis_client.get(f"{_MINUTES_KEY_PREFIX}{task_id}")
        if raw is None:
            data = await self._load_minutes_from_db(task_id, db_session)
            if data is None:
                raise SalesContactBriefSourceNotFoundError(
                    "회의록을 찾을 수 없습니다. 처리가 완료되었는지 확인하세요."
                )
            await redis_client.set(
                f"{_MINUTES_KEY_PREFIX}{task_id}",
                json.dumps(data, ensure_ascii=False),
                ex=settings.minutes_result_ttl,
            )
            return data
        try:
            data = json.loads(cast(str | bytes | bytearray, raw))
        except json.JSONDecodeError as exc:
            raise SalesContactBriefValidationError("회의록 JSON을 해석할 수 없습니다.") from exc
        if not isinstance(data, dict):
            raise SalesContactBriefValidationError("회의록 결과 형식이 올바르지 않습니다.")
        return data

    async def _load_minutes_from_db(
        self,
        task_id: str,
        db_session: AsyncSession | None,
    ) -> dict[str, Any] | None:
        if db_session is None:
            return None
        result = await db_session.execute(
            select(TaskResult).where(
                TaskResult.task_id == task_id,
                TaskResult.task_type == "minutes",
                TaskResult.status == "completed",
            )
        )
        record = result.scalar_one_or_none()
        data = getattr(record, "result_data", None) if record is not None else None
        return dict(data) if isinstance(data, dict) else None

    def _format_transcript(self, minutes_data: dict[str, Any]) -> str:
        segments = minutes_data.get("segments", [])
        if not isinstance(segments, list) or not segments:
            return str(minutes_data.get("raw_text", ""))

        lines = []
        for index, seg in enumerate(segments):
            if not isinstance(seg, dict):
                continue
            speaker = seg.get("speaker_name") or seg.get("speaker") or "알 수 없음"
            text = str(seg.get("text", "")).strip()
            start = seg.get("start", 0.0)
            lines.append(f"[{index} | {start}s | {speaker}] {text}")
        return "\n".join(lines)

    def _extract_source_refs(self, minutes_data: dict[str, Any]) -> list[StudySourceRef]:
        refs: list[StudySourceRef] = []
        segments = minutes_data.get("segments", [])
        if not isinstance(segments, list):
            return refs
        for index, seg in enumerate(segments[:20]):
            if not isinstance(seg, dict):
                continue
            refs.append(
                StudySourceRef(
                    segment_index=index,
                    speaker=seg.get("speaker_name") or seg.get("speaker"),
                    start=seg.get("start"),
                    end=seg.get("end"),
                    text=str(seg.get("text", ""))[:240],
                )
            )
        return refs

    def _build_prompt(self, transcript: str, *, language: str) -> str:
        return f"""다음 영업/고객 대화 녹취록을 바탕으로 고객 후속 브리프를 생성하세요.

## 언어
{language}

## 녹취록
{transcript}

## 지시사항
- 반드시 녹취록에 있는 내용만 사용하세요.
- 고객 신원, 니즈, pain point, objection, 다음 액션을 분리하세요.
- 확인되지 않은 이메일/전화/금액은 null로 두세요.
- follow_up_message는 고객에게 보낼 수 있는 짧은 후속 메시지 초안으로 작성하세요.
- source_refs에는 근거가 되는 세그먼트 인덱스를 넣으세요.
- 아래 JSON 형식만 출력하세요.

{{
  "contact": {{
    "name": "고객명 또는 null",
    "company": "회사명 또는 null",
    "role": "직책 또는 null",
    "email": null,
    "phone": null
  }},
  "deal": {{
    "stage": "lead|qualified|demo_requested|proposal|negotiation|closed|unknown",
    "value_hint": null,
    "urgency": "low|medium|high|unknown"
  }},
  "customer_needs": ["녹취록 기반 고객 니즈"],
  "pain_points": ["녹취록 기반 문제"],
  "objections": ["녹취록 기반 우려/장애물"],
  "next_steps": [
    {{"task": "후속 조치", "owner": "담당자 또는 null", "due": "기한 또는 null"}}
  ],
  "follow_up_message": "후속 메시지 초안",
  "source_refs": [0]
}}"""

    def _parse_response(self, response_text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise SalesContactBriefValidationError("AI 응답이 JSON 형식이 아닙니다.") from exc
        if not isinstance(parsed, dict):
            raise SalesContactBriefValidationError("AI 응답 루트는 객체여야 합니다.")
        return parsed

    def _validate_result(self, result: SalesContactBriefResponse) -> None:
        if not result.next_steps:
            raise SalesContactBriefValidationError("AI 응답에 next_steps가 없습니다.")
        if not result.follow_up_message.strip():
            raise SalesContactBriefValidationError("AI 응답에 follow_up_message가 없습니다.")

    def _build_fallback_result(
        self,
        task_id: str,
        minutes_data: dict[str, Any],
        source_refs: list[StudySourceRef],
    ) -> SalesContactBriefResponse:
        transcript = self._format_transcript(minutes_data)
        excerpt = _first_meaningful_line(transcript)
        need = _short_text(excerpt, 120) or "회의 내용을 검토하고 후속 조치를 정리해야 합니다."
        return SalesContactBriefResponse(
            task_id=task_id,
            contact=SalesContactIdentity(),
            deal=SalesContactDeal(stage="unknown", urgency="unknown"),
            customer_needs=[need],
            pain_points=[],
            objections=[],
            next_steps=[
                SalesNextStep(
                    task="회의 내용 기반 후속 조치를 확인하고 담당자를 지정합니다.",
                    owner=None,
                    due=None,
                )
            ],
            follow_up_message=(
                "회의에서 논의된 내용을 바탕으로 후속 조치를 정리해 공유드리겠습니다."
            ),
            source_refs=source_refs,
            created_at=datetime.now(UTC).isoformat(),
        )


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        normalized = " ".join(line.strip().split())
        if normalized:
            return normalized
    return " ".join(text.strip().split())


def _short_text(text: str, limit: int) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit].rstrip()}..."
