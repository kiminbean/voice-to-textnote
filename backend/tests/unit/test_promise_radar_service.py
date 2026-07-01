import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.device_token_models  # noqa: F401
import backend.db.promise_ledger_models  # noqa: F401
from backend.db.auth_models import MeetingOwnership
from backend.db.device_token_models import DeviceToken
from backend.db.models import ActionItem, TaskResult
from backend.db.promise_ledger_models import PromiseLedgerEntry, PromiseLedgerEvent
from backend.schemas.promise_radar import (
    PromiseLedgerMergeRequest,
    PromiseLedgerSplitRequest,
    PromiseLedgerUpdateRequest,
)
from backend.services.promise_radar_service import PromiseRadarService


@pytest_asyncio.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(TaskResult.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


def _summary_record(
    task_id: str,
    *,
    created_at: datetime,
    action_items: list[dict],
    key_decisions: list[str] | None = None,
    next_steps: list[str] | None = None,
) -> TaskResult:
    return TaskResult(
        task_id=task_id,
        task_type="summary",
        status="completed",
        created_at=created_at,
        completed_at=created_at,
        result_data={
            "summary_text": "테스트 요약",
            "action_items": action_items,
            "key_decisions": key_decisions or [],
            "next_steps": next_steps or [],
        },
    )


def test_promise_radar_detects_continuity_risks():
    service = PromiseRadarService()
    base = datetime(2026, 6, 30, 9, 0, 0)
    previous = [
        _summary_record(
            "sum-prev-1",
            created_at=base - timedelta(days=7),
            action_items=[
                {
                    "task": "모바일 앱 QA 체크리스트 작성",
                    "assignee": "김기수",
                    "deadline": "금요일",
                    "priority": "high",
                },
                {
                    "task": "Hugging Face pyannote 접근 권한 확인",
                    "assignee": "김기수",
                    "priority": "medium",
                },
            ],
            key_decisions=["프로덕션 API URL은 100.69.69.119 IP로 연결한다"],
        ),
        _summary_record(
            "sum-prev-2",
            created_at=base - timedelta(days=21),
            action_items=[
                {
                    "task": "모바일 앱 QA 체크리스트 초안 작성",
                    "assignee": "김기수",
                    "priority": "medium",
                },
            ],
        ),
    ]
    current = _summary_record(
        "sum-current",
        created_at=base,
        action_items=[
            {
                "task": "모바일 앱 QA 체크리스트 마무리",
                "assignee": "김기수",
                "deadline": "오늘",
                "priority": "high",
            }
        ],
        key_decisions=["프로덕션 API URL은 backend.voice 도메인으로 연결한다"],
    )

    result = service.analyze_records(current, previous)

    assert result.task_id == "sum-current"
    assert result.analyzed_meetings == 3
    assert result.current_promises[0].owner == "김기수"
    assert result.carried_over_promises
    assert "QA 체크리스트" in result.carried_over_promises[0].current.text
    assert any("pyannote" in item.text for item in result.stale_promises)
    assert result.decision_drifts
    assert result.promise_chains
    assert result.promise_chains[0].occurrences >= 2
    assert result.promise_chains[0].risk_level in {"medium", "high"}
    assert result.owner_risks
    assert result.owner_risks[0].owner == "김기수"
    assert result.high_risk_count >= 0
    assert result.follow_up_questions
    assert result.risk_score > 0


def test_promise_radar_falls_back_to_next_steps():
    service = PromiseRadarService()
    current = _summary_record(
        "sum-current",
        created_at=datetime(2026, 6, 30, 9, 0, 0),
        action_items=[],
        next_steps=["릴리스 빌드 후 로그인 회귀 테스트를 진행한다"],
    )

    result = service.analyze_records(current, [])

    assert result.current_promises[0].text == "릴리스 빌드 후 로그인 회귀 테스트를 진행한다"
    assert result.current_promises[0].confidence < 0.7
    assert result.promise_chains[0].status == "active"
    assert result.stale_promises == []


def test_semantic_matching_and_korean_due_parser_are_stronger():
    service = PromiseRadarService()
    base = datetime(2026, 7, 1, 10, 0, 0)

    score = service._promise_similarity(
        "모바일 앱 QA 체크리스트 작성",
        "모바일 앱 검증 체크리스트 마무리",
        "김기수",
        "김기수",
    )

    assert score >= 0.5
    assert service._parse_due_at("다음 주 화요일 오전 9시", base) == datetime(
        2026,
        7,
        7,
        9,
        0,
    )
    assert service._parse_due_at("7월 3일 오후 2시 30분", base) == datetime(
        2026,
        7,
        3,
        14,
        30,
    )
    assert service._parse_due_at("3일 후", base) == datetime(2026, 7, 4, 18, 0)


@pytest.mark.asyncio
async def test_build_radar_persists_ledger_with_evidence_and_user_corrections(session_factory):
    service = PromiseRadarService()
    owner_id = uuid.uuid4()
    base = datetime(2026, 6, 30, 9, 0, 0)

    minutes = TaskResult(
        task_id="min-current",
        task_type="minutes",
        status="completed",
        created_at=base,
        completed_at=base,
        result_data={
            "segments": [
                {
                    "speaker_id": "SPEAKER_01",
                    "identified_speaker_name": "김기수",
                    "identified_speaker_profile_id": str(uuid.uuid4()),
                    "voiceprint_similarity": 0.91,
                    "start": 12.3,
                    "end": 18.9,
                    "text": "모바일 앱 QA 체크리스트를 오늘 마무리하겠습니다.",
                }
            ]
        },
    )
    current = _summary_record(
        "sum-current",
        created_at=base,
        action_items=[
            {
                "task": "모바일 앱 QA 체크리스트 마무리",
                "assignee": "김기수",
                "deadline": "오늘",
                "priority": "high",
            }
        ],
    )
    current.input_metadata = {"minutes_task_id": "min-current"}

    async with session_factory() as session:
        session.add_all(
            [
                minutes,
                current,
                MeetingOwnership(task_id="sum-current", owner_id=owner_id),
                MeetingOwnership(task_id="min-current", owner_id=owner_id),
            ]
        )
        await session.commit()

        radar = await service.build_radar(session, "sum-current", owner_id=owner_id)

        assert radar.ledger_entries
        entry = radar.ledger_entries[0]
        assert entry.owner == "김기수"
        assert entry.status == "open"
        assert entry.evidence[0].speaker == "김기수"
        assert entry.evidence[0].start_seconds == 12.3
        assert radar.next_meeting_briefing is not None
        assert radar.next_meeting_briefing.questions

        updated = await service.update_ledger_entry(
            session,
            entry.id,
            PromiseLedgerUpdateRequest(status="completed", user_confirmed=True),
            owner_id=owner_id,
        )

        assert updated.status == "completed"
        assert updated.user_confirmed is True

        stored = (
            await session.execute(
                select(PromiseLedgerEntry).where(PromiseLedgerEntry.id == uuid.UUID(entry.id))
            )
        ).scalar_one()
        assert stored.completed_at is not None


@pytest.mark.asyncio
async def test_create_action_item_from_ledger_entry_is_idempotent(session_factory):
    service = PromiseRadarService()
    owner_id = uuid.uuid4()
    now = datetime.now()

    async with session_factory() as session:
        entry = PromiseLedgerEntry(
            owner_id=owner_id,
            source_task_id="sum-action",
            last_source_task_id="sum-action",
            canonical_key="qa checklist",
            canonical_text="QA 체크리스트 마무리",
            text="QA 체크리스트 마무리",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="high",
            confidence=0.9,
            due_date_text="내일",
            due_at=now + timedelta(days=1),
            occurrences=2,
            first_seen_at=now,
            last_seen_at=now,
            evidence=[
                {
                    "source_task_id": "sum-action",
                    "meeting_link": "/results/sum-action",
                    "transcript": "QA 체크리스트를 마무리하겠습니다.",
                }
            ],
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

        first = await service.create_action_item(session, entry.id, owner_id=owner_id)
        second = await service.create_action_item(session, entry.id, owner_id=owner_id)

        assert first.action_item_id == second.action_item_id
        action_item = (
            await session.execute(
                select(ActionItem).where(ActionItem.id == uuid.UUID(first.action_item_id))
            )
        ).scalar_one()
        assert action_item.title == "QA 체크리스트 마무리"
        assert action_item.priority == "critical"
        assert action_item.category == "promise-radar"


@pytest.mark.asyncio
async def test_next_meeting_briefing_builds_reminder_candidates(session_factory):
    service = PromiseRadarService()
    owner_id = uuid.uuid4()
    due_at = datetime.now() + timedelta(days=1)

    async with session_factory() as session:
        session.add(
            PromiseLedgerEntry(
                owner_id=owner_id,
                source_task_id="sum-brief",
                last_source_task_id="sum-brief",
                canonical_key="qa checklist",
                canonical_text="QA 체크리스트 마무리",
                text="QA 체크리스트 마무리",
                owner_name="김기수",
                status="open",
                priority="high",
                risk_level="medium",
                confidence=0.8,
                due_date_text="내일",
                due_at=due_at,
                occurrences=2,
                first_seen_at=datetime.now(),
                last_seen_at=datetime.now(),
                evidence=[
                    {
                        "source_task_id": "sum-brief",
                        "meeting_link": "/results/sum-brief",
                        "transcript": "QA 체크리스트를 마무리하겠습니다.",
                    }
                ],
            )
        )
        await session.commit()

        briefing = await service.build_next_meeting_briefing(session, owner_id=owner_id)

        assert briefing.due_soon_count == 1
        assert briefing.owner_hotspots[0].owner == "김기수"
        assert briefing.reminder_candidates[0].calendar_event["source"] == "promise_radar"


class _FakePushService:
    def __init__(self) -> None:
        self.sent_payloads = []
        self.invalidated_tokens = []

    async def send_multicast(self, tokens, title, body, data=None):
        self.sent_payloads.append(
            {
                "tokens": tokens,
                "title": title,
                "body": body,
                "data": data or {},
            }
        )
        return {"success_count": len(tokens), "failure_count": 0, "invalid_tokens": []}

    async def invalidate_token(self, db, fcm_token):
        self.invalidated_tokens.append(fcm_token)


@pytest.mark.asyncio
async def test_ledger_merge_split_history_dashboard_and_due_push(session_factory):
    service = PromiseRadarService()
    owner_id = uuid.uuid4()
    now = datetime.now()

    async with session_factory() as session:
        target = PromiseLedgerEntry(
            owner_id=owner_id,
            source_task_id="sum-target",
            last_source_task_id="sum-target",
            canonical_key="검증 체크리스트",
            canonical_text="모바일 앱 검증 체크리스트",
            text="모바일 앱 검증 체크리스트",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="medium",
            confidence=0.82,
            due_date_text="내일",
            due_at=now + timedelta(days=1),
            occurrences=1,
            first_seen_at=now,
            last_seen_at=now,
            evidence=[
                {
                    "source_task_id": "sum-target",
                    "meeting_link": "/results/sum-target",
                    "transcript": "검증 체크리스트를 마무리하겠습니다.",
                }
            ],
        )
        duplicate = PromiseLedgerEntry(
            owner_id=owner_id,
            source_task_id="sum-dup",
            last_source_task_id="sum-dup",
            canonical_key="qa 체크리스트",
            canonical_text="모바일 앱 QA 체크리스트",
            text="모바일 앱 QA 체크리스트",
            owner_name="김기수",
            status="open",
            priority="medium",
            risk_level="low",
            confidence=0.78,
            occurrences=1,
            first_seen_at=now - timedelta(days=2),
            last_seen_at=now - timedelta(days=2),
            evidence=[
                {
                    "source_task_id": "sum-dup",
                    "meeting_link": "/results/sum-dup",
                    "transcript": "QA 체크리스트를 작성하겠습니다.",
                }
            ],
        )
        due_entry = PromiseLedgerEntry(
            owner_id=owner_id,
            source_task_id="sum-due",
            last_source_task_id="sum-due",
            canonical_key="배포 확인",
            canonical_text="배포 확인",
            text="배포 확인",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="high",
            confidence=0.9,
            due_date_text="오늘",
            due_at=now - timedelta(minutes=5),
            reminder_at=now - timedelta(minutes=10),
            occurrences=1,
            first_seen_at=now,
            last_seen_at=now,
        )
        session.add_all(
            [
                target,
                duplicate,
                due_entry,
                DeviceToken(
                    user_id=str(owner_id),
                    fcm_token="fcm-token-1",
                    platform="ios",
                    is_active=True,
                ),
            ]
        )
        await session.commit()
        await session.refresh(target)
        await session.refresh(duplicate)
        await session.refresh(due_entry)

        merged = await service.merge_ledger_entries(
            session,
            target.id,
            PromiseLedgerMergeRequest(source_entry_ids=[str(duplicate.id)], note="same promise"),
            owner_id=owner_id,
        )
        assert merged.target.occurrences == 2
        assert merged.merged_entry_ids == [str(duplicate.id)]

        duplicate_after = (
            await session.execute(
                select(PromiseLedgerEntry).where(PromiseLedgerEntry.id == duplicate.id)
            )
        ).scalar_one()
        assert duplicate_after.status == "dismissed"
        assert duplicate_after.dismissed_reason == f"merged_into:{target.id}"

        split = await service.split_ledger_entry(
            session,
            target.id,
            PromiseLedgerSplitRequest(
                text="Android 릴리스 빌드 회귀 테스트",
                owner="김기수",
                due_date="다음 주 월요일",
            ),
            owner_id=owner_id,
        )
        assert split.created.text == "Android 릴리스 빌드 회귀 테스트"
        assert split.created.due_at is not None

        history = await service.list_ledger_history(session, target.id, owner_id=owner_id)
        assert {item.event_type for item in history} >= {"merged", "split"}

        dashboard = await service.build_dashboard(session, owner_id=owner_id)
        assert dashboard.open_count >= 2
        assert dashboard.high_risk_count >= 1
        assert dashboard.urgent_promises

        fake_push = _FakePushService()
        dispatch = await service.dispatch_due_notifications(
            session,
            owner_id=owner_id,
            now=now,
            push_service=fake_push,
        )
        assert dispatch.sent_count == 1
        assert dispatch.notified_entry_ids == [str(due_entry.id)]
        assert fake_push.sent_payloads[0]["data"]["ledger_entry_id"] == str(due_entry.id)

        event_types = {
            event.event_type
            for event in (
                await session.execute(select(PromiseLedgerEvent))
            ).scalars()
        }
        assert {"merged", "split", "split_created", "notification_sent"}.issubset(event_types)
