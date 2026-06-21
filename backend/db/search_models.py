"""
검색 인덱스 모델 - SPEC-SEARCH-001

SQLite FTS5 기반 전문 검색 인덱스 관리
- ensure_search_index_table(): FTS5 가상 테이블 생성
- index_search_entry(): 검색 인덱스 항목 추가/갱신 (upsert)
- delete_search_entry(): 검색 인덱스 항목 삭제

ORM 모델이 아닌 Raw SQL을 사용합니다.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Connection, Engine, text
from sqlalchemy.orm import Session

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# FTS5 가상 테이블 생성 SQL (unicode61 토크나이저 - 한국어 지원)
_CREATE_FTS5_TABLE_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS search_index
USING fts5(
    task_id,
    task_type,
    content,
    speaker_names,
    summary_text,
    action_items_text,
    created_at UNINDEXED,
    tokenize='unicode61'
)
"""

# 검색 인덱스 삭제 SQL
_DELETE_ENTRY_SQL = "DELETE FROM search_index WHERE task_id = :task_id"
_DELETE_ENTRY_FOR_TYPE_SQL = (
    "DELETE FROM search_index WHERE task_id = :task_id AND task_type = :task_type"
)

# 검색 인덱스 삽입 SQL
_INSERT_ENTRY_SQL = """
INSERT INTO search_index
    (task_id, task_type, content, speaker_names, summary_text, action_items_text, created_at)
VALUES
    (:task_id, :task_type, :content, :speaker_names, :summary_text, :action_items_text, :created_at)
"""

# 인덱싱 대상 타입
_INDEXABLE_TASK_TYPES = {"minutes", "summary", "sales_contact_brief"}


def ensure_search_index_table(engine_or_connection: Engine | Connection) -> None:
    """
    FTS5 search_index 가상 테이블 생성 (없으면 생성, 있으면 무시)

    Args:
        engine_or_connection: SQLAlchemy Engine 또는 Connection 객체
    """
    if isinstance(engine_or_connection, Connection):
        engine_or_connection.execute(text(_CREATE_FTS5_TABLE_SQL))
    else:
        with engine_or_connection.connect() as conn:
            conn.execute(text(_CREATE_FTS5_TABLE_SQL))
            conn.commit()


def index_search_entry(
    session: Session,
    task_id: str,
    task_type: str,
    result_data: dict,
    created_at: datetime | None = None,
) -> None:
    """
    검색 인덱스에 항목 추가 또는 갱신 (best-effort)

    minutes, summary, sales_contact_brief 타입만 인덱싱합니다.
    FTS5는 UPDATE를 지원하지 않으므로 DELETE + INSERT로 upsert 처리합니다.
    예외가 발생해도 re-raise하지 않습니다 (best-effort).

    Args:
        session: SQLAlchemy 동기 세션
        task_id: 작업 ID
        task_type: 작업 유형 (minutes, summary, sales_contact_brief만 처리)
        result_data: 결과 데이터 JSON
        created_at: 생성 시각 (None이면 현재 시각 사용)
    """
    # 인덱싱 대상 타입이 아니면 스킵
    if task_type not in _INDEXABLE_TASK_TYPES:
        return

    try:
        # 인덱싱 데이터 추출
        content, speaker_names, summary_text, action_items_text = _extract_index_data(
            task_type, result_data
        )

        created_at_str = (
            created_at.isoformat()
            if created_at
            else datetime.now(UTC).replace(tzinfo=None).isoformat()
        )

        # FTS5 upsert: 기존 항목 삭제 후 재삽입
        session.execute(
            text(_DELETE_ENTRY_FOR_TYPE_SQL),
            {"task_id": task_id, "task_type": task_type},
        )
        session.execute(
            text(_INSERT_ENTRY_SQL),
            {
                "task_id": task_id,
                "task_type": task_type,
                "content": content,
                "speaker_names": speaker_names,
                "summary_text": summary_text,
                "action_items_text": action_items_text,
                "created_at": created_at_str,
            },
        )
    except Exception as e:
        # best-effort: 예외 로그 후 무시
        logger.warning(
            "검색 인덱스 추가 실패 (무시)",
            task_id=task_id,
            task_type=task_type,
            error=str(e),
        )


def delete_search_entry(session: Session, task_id: str) -> None:
    """
    검색 인덱스에서 항목 삭제

    Args:
        session: SQLAlchemy 동기 세션
        task_id: 삭제할 작업 ID
    """
    try:
        session.execute(text(_DELETE_ENTRY_SQL), {"task_id": task_id})
    except Exception as e:
        logger.warning(
            "검색 인덱스 삭제 실패 (무시)",
            task_id=task_id,
            error=str(e),
        )


def _extract_index_data(
    task_type: str,
    result_data: dict,
) -> tuple[str, str, str, str]:
    """
    task_type에 따라 인덱싱 데이터 추출

    Returns:
        (content, speaker_names, summary_text, action_items_text)
    """
    content = ""
    speaker_names = ""
    summary_text = ""
    action_items_text = ""

    if task_type == "minutes":
        # segments의 텍스트를 합쳐 content 생성
        segments = result_data.get("segments", [])
        content = " ".join(seg.get("text", "") for seg in segments if seg.get("text"))
        translation_terms = _extract_translation_terms(result_data.get("translations"))
        if translation_terms:
            content = " ".join(part for part in (content, " ".join(translation_terms)) if part)

        # 화자 이름 추출
        speakers = result_data.get("speakers", [])
        speaker_name_list = [s.get("speaker_name", "") for s in speakers if s.get("speaker_name")]
        # segments의 화자 이름도 추가 (중복 제거)
        for seg in segments:
            name = seg.get("speaker_name", "")
            if name and name not in speaker_name_list:
                speaker_name_list.append(name)
        speaker_names = " ".join(speaker_name_list)

    elif task_type == "summary":
        # 요약 텍스트
        summary_text = result_data.get("summary_text", "")
        translation_terms = _extract_translation_terms(result_data.get("translations"))
        if translation_terms:
            summary_text = " ".join(
                part for part in (summary_text, " ".join(translation_terms)) if part
            )
        study_pack = result_data.get("study_pack")
        if isinstance(study_pack, dict):
            study_notes = str(study_pack.get("study_notes", "")).strip()
            if study_notes:
                summary_text = " ".join(part for part in (summary_text, study_notes) if part)

        # action_items, key_decisions, next_steps를 합쳐 action_items_text 생성
        parts = []
        for item in result_data.get("action_items", []):
            task = item.get("task", "")
            if task:
                parts.append(task)
        for decision in result_data.get("key_decisions", []):
            if decision:
                parts.append(decision)
        for step in result_data.get("next_steps", []):
            if step:
                parts.append(step)
        if isinstance(study_pack, dict):
            parts.extend(_extract_study_pack_terms(study_pack))
        action_items_text = " ".join(parts)

    elif task_type == "sales_contact_brief":
        content, summary_text, action_items_text = _extract_sales_contact_brief_terms(
            result_data
        )

    return content, speaker_names, summary_text, action_items_text


def _extract_sales_contact_brief_terms(result_data: dict) -> tuple[str, str, str]:
    """Flatten a generated sales/contact brief into searchable fields."""
    contact = result_data.get("contact")
    deal = result_data.get("deal")
    contact_parts: list[str] = []
    summary_parts: list[str] = []
    action_parts: list[str] = []

    if isinstance(contact, dict):
        for field in ("name", "company", "role", "email", "phone"):
            value = str(contact.get(field, "") or "").strip()
            if value:
                contact_parts.append(value)

    if isinstance(deal, dict):
        for field in ("stage", "value_hint", "urgency"):
            value = str(deal.get(field, "") or "").strip()
            if value:
                summary_parts.append(value)

    for field in ("customer_needs", "pain_points", "objections"):
        values = result_data.get(field) or []
        if not isinstance(values, list):
            continue
        for item in values:
            value = str(item).strip()
            if value:
                summary_parts.append(value)

    follow_up_message = str(result_data.get("follow_up_message", "") or "").strip()
    if follow_up_message:
        summary_parts.append(follow_up_message)

    for item in result_data.get("next_steps") or []:
        if not isinstance(item, dict):
            continue
        for field in ("task", "owner", "due"):
            value = str(item.get(field, "") or "").strip()
            if value:
                action_parts.append(value)

    return " ".join(contact_parts), " ".join(summary_parts), " ".join(action_parts)


def _extract_study_pack_terms(study_pack: dict) -> list[str]:
    """Flatten Study Pack learning artifacts into searchable text."""
    parts: list[str] = []

    for item in study_pack.get("key_concepts", []) or []:
        if not isinstance(item, dict):
            continue
        for field in ("term", "explanation"):
            value = str(item.get(field, "")).strip()
            if value:
                parts.append(value)

    for item in study_pack.get("flashcards", []) or []:
        if not isinstance(item, dict):
            continue
        for field in ("front", "back"):
            value = str(item.get(field, "")).strip()
            if value:
                parts.append(value)

    for item in study_pack.get("quiz_questions", []) or []:
        if not isinstance(item, dict):
            continue
        for field in ("question", "answer"):
            value = str(item.get(field, "")).strip()
            if value:
                parts.append(value)

    return parts


def _extract_translation_terms(translations: object) -> list[str]:
    """Flatten cached translation payloads into searchable text."""
    if not isinstance(translations, dict):
        return []

    parts: list[str] = []
    seen: set[str] = set()
    for payload in translations.values():
        if not isinstance(payload, dict):
            continue
        text_value = str(payload.get("translated_text", "")).strip()
        if text_value and text_value not in seen:
            seen.add(text_value)
            parts.append(text_value)
    return parts
