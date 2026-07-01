import uuid
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import backend.db.auth_models  # noqa: F401
import backend.db.device_token_models  # noqa: F401
import backend.db.promise_ledger_models  # noqa: F401
from backend.db.auth_models import MeetingOwnership, Team, TeamMember, User
from backend.db.device_token_models import DeviceToken
from backend.db.models import ActionItem, TaskResult
from backend.db.promise_ledger_models import PromiseLedgerEntry, PromiseLedgerEvent
from backend.schemas.promise_radar import (
    PromiseAccuracyCase,
    PromiseAutomationPolicyUpdateRequest,
    PromiseAutopilotConfirmRequest,
    PromiseAutopilotRejectRequest,
    PromiseConflictResolveRequest,
    PromiseDigestPreferenceUpdateRequest,
    PromiseExternalExportRequest,
    PromiseExternalTaskUpdateRequest,
    PromiseLearningFeedbackRequest,
    PromiseLedgerMergeRequest,
    PromiseLedgerSplitRequest,
    PromiseLedgerUpdateRequest,
)
from backend.scripts.audit_promise_radar_accuracy_set import audit_accuracy_set
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

        digest_dispatch = await service.dispatch_digest_notifications(
            session,
            owner_id=owner_id,
            now=now,
            push_service=fake_push,
        )
        assert digest_dispatch.sent_count == 1
        assert fake_push.sent_payloads[-1]["data"]["type"] == "promise_radar_digest"
        duplicate_digest = await service.dispatch_digest_notifications(
            session,
            owner_id=owner_id,
            now=now,
            push_service=fake_push,
        )
        assert duplicate_digest.sent_count == 0

        event_types = {
            event.event_type
            for event in (await session.execute(select(PromiseLedgerEvent))).scalars()
        }
        assert {
            "merged",
            "split",
            "split_created",
            "notification_sent",
            "digest_notification_sent",
        }.issubset(event_types)


@pytest.mark.asyncio
async def test_promise_autopilot_calendar_assignee_and_quality(session_factory):
    service = PromiseRadarService()
    owner_id = uuid.uuid4()
    teammate_id = uuid.uuid4()
    team_id = uuid.uuid4()
    now = datetime(2026, 7, 1, 9, 0, 0)

    current = _summary_record(
        "sum-autopilot",
        created_at=now,
        action_items=[],
        next_steps=["QA 체크리스트 작성 완료했습니다."],
    )
    minutes = TaskResult(
        task_id="min-autopilot",
        task_type="minutes",
        status="completed",
        created_at=now,
        completed_at=now,
        result_data={
            "segments": [
                {
                    "speaker_id": "SPEAKER_01",
                    "identified_speaker_name": "김기수",
                    "start": 5.0,
                    "end": 9.0,
                    "text": "QA 체크리스트 작성 완료했습니다.",
                }
            ]
        },
    )
    current.input_metadata = {"minutes_task_id": "min-autopilot"}

    async with session_factory() as session:
        entry = PromiseLedgerEntry(
            owner_id=owner_id,
            team_id=team_id,
            source_task_id="sum-source",
            last_source_task_id="sum-source",
            canonical_key="qa 체크리스트 작성",
            canonical_text="QA 체크리스트 작성",
            text="QA 체크리스트 작성",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="medium",
            confidence=0.86,
            due_date_text="오늘",
            due_at=now + timedelta(hours=3),
            occurrences=2,
            first_seen_at=now - timedelta(days=7),
            last_seen_at=now - timedelta(days=7),
            evidence=[
                {
                    "source_task_id": "sum-source",
                    "meeting_link": "/results/sum-source",
                    "transcript": "QA 체크리스트를 작성하겠습니다.",
                }
            ],
        )
        confirm_entry = PromiseLedgerEntry(
            owner_id=owner_id,
            team_id=team_id,
            source_task_id="sum-source-confirm",
            last_source_task_id="sum-source-confirm",
            canonical_key="qa 체크리스트 작성 confirm",
            canonical_text="QA 체크리스트 작성",
            text="QA 체크리스트 작성",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="medium",
            confidence=0.86,
            due_date_text="오늘",
            due_at=now + timedelta(hours=3),
            occurrences=2,
            first_seen_at=now - timedelta(days=7),
            last_seen_at=now - timedelta(days=7),
            evidence=[
                {
                    "source_task_id": "sum-source-confirm",
                    "meeting_link": "/results/sum-source-confirm",
                    "transcript": "QA 체크리스트를 작성하겠습니다.",
                    "speaker_label": "SPEAKER_01",
                }
            ],
        )
        session.add_all(
            [
                User(
                    id=owner_id,
                    email="owner@example.com",
                    display_name="소유자",
                    password_hash="hash",
                ),
                User(
                    id=teammate_id,
                    email="kiminbean@example.com",
                    display_name="김기수",
                    password_hash="hash",
                ),
                Team(id=team_id, name="테스트 팀", created_by=owner_id),
                TeamMember(team_id=team_id, user_id=owner_id, role="admin"),
                TeamMember(team_id=team_id, user_id=teammate_id, role="member"),
                TaskResult(
                    task_id="sum-source",
                    task_type="summary",
                    status="completed",
                    created_at=now - timedelta(days=7),
                    completed_at=now - timedelta(days=7),
                    result_data={"action_items": []},
                ),
                current,
                minutes,
                MeetingOwnership(task_id="sum-autopilot", owner_id=owner_id, team_id=team_id),
                MeetingOwnership(task_id="min-autopilot", owner_id=owner_id, team_id=team_id),
                entry,
                confirm_entry,
            ]
        )
        await session.commit()
        await session.refresh(entry)
        await session.refresh(confirm_entry)

        preview = await service.run_autopilot(
            session,
            "sum-autopilot",
            owner_id=owner_id,
            team_id=team_id,
            apply=False,
        )
        assert preview.preview_mode is True
        assert preview.applied_count == 0
        assert preview.status_thresholds["completed"] >= 0.62
        assert preview.assessments[0].requires_confirmation is True
        assert preview.assessments[0].evidence_pack is not None
        assert preview.assessments[0].evidence_pack.marker_hits

        review_queue = await service.build_autopilot_review_queue(
            session,
            "sum-autopilot",
            owner_id=owner_id,
            team_id=team_id,
        )
        assert review_queue.queue_count >= 2
        assert review_queue.actionable_count >= 2
        assert review_queue.items[0].ledger_entry.text
        assert review_queue.items[0].assessment.evidence_pack is not None

        confirmed = await service.confirm_autopilot_assessment(
            session,
            confirm_entry.id,
            PromiseAutopilotConfirmRequest(
                task_id="sum-autopilot",
                suggested_status="completed",
                note="미리보기 확인",
            ),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert confirmed.applied is True
        assert confirmed.requires_confirmation is False
        confirmed_stored = (
            await session.execute(
                select(PromiseLedgerEntry).where(PromiseLedgerEntry.id == confirm_entry.id)
            )
        ).scalar_one()
        assert confirmed_stored.status == "completed"
        assert confirmed_stored.user_confirmed is True
        latest_pack = await service.latest_evidence_pack(
            session,
            confirm_entry.id,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert latest_pack.ledger_entry_id == str(confirm_entry.id)
        assert latest_pack.marker_hits
        comparison = await service.evidence_comparison(
            session,
            confirm_entry.id,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert comparison.current_pack is not None
        assert comparison.current_similarity is not None
        assert comparison.shared_terms

        autopilot = await service.run_autopilot(
            session,
            "sum-autopilot",
            owner_id=owner_id,
            team_id=team_id,
        )

        assert autopilot.assessed_count == 1
        assert autopilot.applied_count == 1
        assert autopilot.assessments[0].suggested_status == "completed"
        assert autopilot.assessments[0].confidence >= 0.68

        stored = (
            await session.execute(
                select(PromiseLedgerEntry).where(PromiseLedgerEntry.id == entry.id)
            )
        ).scalar_one()
        assert stored.status == "completed"
        assert stored.completed_at is not None

        explanation = await service.explain_ledger_entry_match(
            session,
            entry.id,
            task_id="sum-autopilot",
            owner_id=owner_id,
            team_id=team_id,
        )
        assert explanation.similarity > 0
        assert "확인" in explanation.overlap_terms

        calendar = await service.export_calendar_event(
            session,
            entry.id,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert "BEGIN:VCALENDAR" in calendar.ics_content
        assert f"X-VOICE-TEXTNOTE-PROMISE-ID:{entry.id}" in calendar.ics_content
        assert calendar.google_calendar_url.startswith("https://calendar.google.com/")

        suggestions = await service.suggest_assignees(
            session,
            entry.id,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert suggestions[0].user_id == str(teammate_id)
        assert suggestions[0].confidence >= 0.9
        entry.owner_name = "기수님"
        nickname_suggestions = await service.suggest_assignees(
            session,
            entry.id,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert nickname_suggestions[0].user_id == str(teammate_id)
        assert nickname_suggestions[0].confidence >= 0.9
        entry.owner_name = "김기수"

        response = service._entry_to_response(stored)
        assert response.quality is not None
        assert response.quality.score >= 70
        assert autopilot.autopilot_threshold >= 0.62
        assert autopilot.evidence_lock_enforced is True

        weak_evidence = autopilot.assessments[0].model_copy(
            update={
                "explanation": autopilot.assessments[0].explanation.model_copy(
                    update={"similarity": 0.1}
                )
            }
        )
        assert (
            service._should_apply_autopilot(
                weak_evidence,
                threshold=0.1,
                evidence_lock_enabled=True,
            )
            is False
        )
        assert (
            service._should_apply_autopilot(
                weak_evidence,
                threshold=0.1,
                evidence_lock_enabled=False,
            )
            is True
        )
        short_marker_only = autopilot.assessments[0].model_copy(
            update={
                "confidence": 0.95,
                "explanation": autopilot.assessments[0].explanation.model_copy(
                    update={
                        "matched_text": "done",
                        "similarity": 0.95,
                    }
                ),
                "evidence_pack": autopilot.assessments[0].evidence_pack.model_copy(
                    update={
                        "matched_text": "done",
                        "similarity": 0.95,
                        "marker_hits": ["done"],
                    }
                ),
            }
        )
        assert (
            service._should_apply_autopilot(
                short_marker_only,
                threshold=0.1,
                evidence_lock_enabled=True,
            )
            is False
        )

        feedback = await service.record_learning_feedback(
            session,
            entry.id,
            PromiseLearningFeedbackRequest(
                expected_status="open",
                predicted_status="completed",
                correction_type="autopilot",
                note="완료 아님",
            ),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert feedback.recorded is True
        assert feedback.learning_profile.false_positive_count == 1
        assert feedback.learning_profile.autopilot_threshold > autopilot.autopilot_threshold
        assert feedback.learning_profile.status_false_positive_count["completed"] == 1
        assert (
            feedback.learning_profile.status_thresholds["completed"]
            > feedback.learning_profile.status_thresholds["delayed"]
        )
        assert any(
            alias.alias == "SPEAKER_01" and alias.canonical_owner == "김기수"
            for alias in feedback.learning_profile.owner_aliases
        )

        timeline = await service.build_ledger_timeline(
            session,
            entry.id,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert {item.event_type for item in timeline.items} >= {
            "autopilot_applied",
            "learning_feedback",
        }

        open_entry = PromiseLedgerEntry(
            owner_id=owner_id,
            team_id=team_id,
            source_task_id="sum-open",
            last_source_task_id="sum-open",
            canonical_key="release note review",
            canonical_text="릴리스 노트 검토",
            text="릴리스 노트 검토",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="high",
            confidence=0.84,
            due_date_text="어제",
            due_at=now - timedelta(days=1),
            occurrences=2,
            first_seen_at=now - timedelta(days=3),
            last_seen_at=now - timedelta(days=1),
            evidence=[
                {
                    "source_task_id": "sum-open",
                    "meeting_link": "/results/sum-open",
                    "transcript": "릴리스 노트를 검토하겠습니다.",
                }
            ],
        )
        session.add(open_entry)
        await session.commit()
        await session.refresh(open_entry)

        pre_meeting = await service.build_pre_meeting_brief(
            session,
            owner_id=owner_id,
            team_id=team_id,
            limit=3,
        )
        assert pre_meeting.readiness_score < 100
        assert pre_meeting.promises[0].id == str(open_entry.id)
        assert pre_meeting.questions
        assert pre_meeting.checkpoints
        assert "김기수" in pre_meeting.checkpoints[0]

        digest = await service.build_digest(
            session,
            owner_id=owner_id,
            team_id=team_id,
            cadence="daily",
        )
        assert digest.overdue_count == 1
        assert any("기한 초과 1개" in line for line in digest.lines)
        default_preference = await service.get_digest_preference(
            session,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert default_preference.enabled is False
        saved_preference = await service.update_digest_preference(
            session,
            PromiseDigestPreferenceUpdateRequest(enabled=True, cadence="daily"),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert saved_preference.enabled is True
        fetched_preference = await service.get_digest_preference(
            session,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert fetched_preference.cadence == "daily"

        slack = await service.export_external_task(
            session,
            open_entry.id,
            PromiseExternalExportRequest(provider="slack", dry_run=True),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert slack.sent is False
        assert slack.payload["text"].startswith("Promise Radar:")
        assert slack.payload["blocks"]

        google_task = await service.export_external_task(
            session,
            open_entry.id,
            PromiseExternalExportRequest(provider="google_tasks", dry_run=True),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert google_task.sent is False
        assert google_task.payload["endpoint"].endswith("/lists/@default/tasks")
        assert google_task.payload["task"]["title"] == "릴리스 노트 검토"
        assert google_task.payload["task"]["due"].endswith("Z")

        conflict_current = _summary_record(
            "sum-conflict",
            created_at=now,
            action_items=[],
            next_steps=["릴리스 노트 검토 완료했습니다. 하지만 아직 못했습니다."],
        )
        session.add(MeetingOwnership(task_id="sum-conflict", owner_id=owner_id, team_id=team_id))
        session.add(conflict_current)
        await session.commit()
        conflict = await service.run_autopilot(
            session,
            "sum-conflict",
            owner_id=owner_id,
            team_id=team_id,
        )
        conflict_assessment = next(
            item for item in conflict.assessments if item.ledger_entry_id == str(open_entry.id)
        )
        assert conflict_assessment.conflict_detected is True
        assert conflict_assessment.applied is False

        conflict_queue = await service.build_autopilot_review_queue(
            session,
            "sum-conflict",
            owner_id=owner_id,
            team_id=team_id,
        )
        assert conflict_queue.conflict_count >= 1
        resolved = await service.resolve_autopilot_conflict(
            session,
            open_entry.id,
            PromiseConflictResolveRequest(status="delayed", note="충돌은 지연으로 해결"),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert resolved.status == "delayed"
        assert resolved.user_confirmed is True

        default_policy = await service.get_automation_policy(
            session,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert default_policy.mode == "safe_auto"
        saved_policy = await service.update_automation_policy(
            session,
            PromiseAutomationPolicyUpdateRequest(
                mode="completed_only",
                allowed_auto_statuses=["completed"],
            ),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert saved_policy.mode == "completed_only"
        fetched_policy = await service.get_automation_policy(
            session,
            owner_id=owner_id,
            team_id=team_id,
        )
        assert fetched_policy.allowed_auto_statuses == ["completed"]

        evaluation = service.evaluate_accuracy_cases(
            [
                PromiseAccuracyCase(
                    id="completed-1",
                    entry_text="QA 체크리스트 작성",
                    current_text="QA 체크리스트 작성 완료했습니다.",
                    expected_status="completed",
                    owner="김기수",
                ),
                PromiseAccuracyCase(
                    id="delayed-1",
                    entry_text="릴리스 노트 검토",
                    current_text="오늘은 다른 안건만 논의했습니다.",
                    expected_status="delayed",
                    owner="김기수",
                    due_at=now - timedelta(days=1),
                ),
            ]
        )
        assert evaluation.case_count == 2
        assert evaluation.correct_count == 2
        assert evaluation.confidence_buckets
        report = service.build_accuracy_report(
            [
                PromiseAccuracyCase(
                    id="real-v10-video1-case",
                    entry_text="QA 체크리스트 작성",
                    current_text="QA 체크리스트 작성 완료했습니다.",
                    expected_status="completed",
                    owner="김기수",
                )
            ],
            fixture_path="backend/tests/fixtures/promise_radar_accuracy_cases.json",
            source_manifest_path="backend/tests/fixtures/promise_radar_real_meeting_sources.json",
            target_case_count=1,
        )
        assert report.real_meeting_case_count == 1
        assert report.source_counts["video1"] == 1
        assert report.coverage["real_meeting_target"] == 1.0
        assert report.evaluation.confidence_buckets
        assert report.source_quality
        assert report.below_target is False

        event_types = {
            event.event_type
            for event in (await session.execute(select(PromiseLedgerEvent))).scalars()
        }
        assert {
            "autopilot_applied",
            "calendar_export_created",
            "learning_feedback",
            "conflict_resolved",
            "automation_policy_updated",
        }.issubset(event_types)


def test_digest_preference_due_window_and_quiet_hours():
    service = PromiseRadarService()
    preference = service._digest_preference_from_value(
        {
            "enabled": True,
            "cadence": "daily",
            "local_time": "08:30",
            "timezone": "Asia/Seoul",
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
        },
        scope="owner:test",
        updated_at=datetime(2026, 7, 1, 0, 0, 0),
    )

    assert service._digest_preference_due_now(
        preference,
        datetime(2026, 6, 30, 23, 45, 0),
    )
    assert not service._digest_preference_due_now(
        preference,
        datetime(2026, 7, 1, 2, 0, 0),
    )
    assert not service._digest_preference_due_now(
        preference,
        datetime(2026, 7, 1, 14, 30, 0),
    )


@pytest.mark.asyncio
async def test_update_external_google_task_pushes_ledger_state(session_factory, monkeypatch):
    service = PromiseRadarService()
    owner_id = uuid.uuid4()
    now = datetime(2026, 7, 1, 9, 0, 0)
    calls: list[dict] = []

    class _FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "status": "completed",
                "selfLink": "https://tasks.googleapis.com/tasks/v1/lists/@default/tasks/task-1",
            }

    class _FakeAsyncClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def patch(self, endpoint, headers, json):
            calls.append({"endpoint": endpoint, "headers": headers, "json": json})
            return _FakeResponse()

    monkeypatch.setattr(
        "backend.services.promise_radar_service.httpx.AsyncClient",
        _FakeAsyncClient,
    )

    async with session_factory() as session:
        entry = PromiseLedgerEntry(
            owner_id=owner_id,
            source_task_id="sum-google-task",
            last_source_task_id="sum-google-task",
            canonical_key="release note review",
            canonical_text="릴리스 노트 검토",
            text="릴리스 노트 검토",
            owner_name="김기수",
            status="completed",
            priority="high",
            risk_level="high",
            confidence=0.9,
            occurrences=1,
            first_seen_at=now,
            last_seen_at=now,
            calendar_event={
                "external_tasks": {
                    "google_tasks": {
                        "external_id": "task-1",
                        "tasklist": "@default",
                    }
                }
            },
        )
        session.add(entry)
        await session.commit()
        await session.refresh(entry)

        response = await service.update_external_task(
            session,
            entry.id,
            PromiseExternalTaskUpdateRequest(access_token="token"),
            owner_id=owner_id,
        )

        assert response.synced is True
        assert response.status == "completed"
        assert response.sync_contract is not None
        assert response.sync_contract["idempotency_key"] == f"promise:google_tasks:{entry.id}"
        assert calls[0]["endpoint"].endswith("/lists/@default/tasks/task-1")
        assert calls[0]["endpoint"].count("/tasks/task-1") == 1
        assert calls[0]["json"]["status"] == "completed"


@pytest.mark.asyncio
async def test_autopilot_review_rejection_removes_candidate(session_factory):
    service = PromiseRadarService()
    now = datetime(2026, 7, 1, 9, 0, 0)
    owner_id = uuid.uuid4()
    team_id = uuid.uuid4()

    async with session_factory() as session:
        entry = PromiseLedgerEntry(
            owner_id=owner_id,
            team_id=team_id,
            source_task_id="sum-review-source",
            last_source_task_id="sum-review-source",
            canonical_key="release note review",
            canonical_text="릴리스 노트 검토",
            text="릴리스 노트 검토",
            owner_name="김기수",
            status="open",
            priority="high",
            risk_level="high",
            confidence=0.86,
            occurrences=1,
            first_seen_at=now - timedelta(days=2),
            last_seen_at=now - timedelta(days=2),
            evidence=[
                {
                    "source_task_id": "sum-review-source",
                    "meeting_link": "/results/sum-review-source",
                    "transcript": "릴리스 노트를 검토하겠습니다.",
                }
            ],
        )
        session.add_all(
            [
                User(
                    id=owner_id,
                    email="review-owner@example.com",
                    display_name="검토자",
                    password_hash="hash",
                ),
                Team(id=team_id, name="리뷰 팀", created_by=owner_id),
                TeamMember(team_id=team_id, user_id=owner_id, role="admin"),
                TaskResult(
                    task_id="sum-review",
                    task_type="summary",
                    status="completed",
                    created_at=now,
                    completed_at=now,
                    result_data={
                        "summary_text": "릴리스 노트 검토 완료",
                        "action_items": [],
                        "key_decisions": [],
                        "next_steps": ["릴리스 노트 검토 완료했습니다."],
                    },
                ),
                MeetingOwnership(task_id="sum-review", owner_id=owner_id, team_id=team_id),
                entry,
            ]
        )
        await session.commit()
        await session.refresh(entry)

        queue = await service.build_autopilot_review_queue(
            session,
            "sum-review",
            owner_id=owner_id,
            team_id=team_id,
        )
        assert queue.queue_count == 1
        assessment = queue.items[0].assessment

        rejected = await service.reject_autopilot_review_item(
            session,
            entry.id,
            PromiseAutopilotRejectRequest(
                task_id="sum-review",
                suggested_status=assessment.suggested_status,
                note="완료 아님",
            ),
            owner_id=owner_id,
            team_id=team_id,
        )
        assert rejected.recorded is True

        queue_after = await service.build_autopilot_review_queue(
            session,
            "sum-review",
            owner_id=owner_id,
            team_id=team_id,
        )
        assert queue_after.queue_count == 0

        event_types = {
            event.event_type
            for event in (await session.execute(select(PromiseLedgerEvent))).scalars()
        }
        assert {"autopilot_review_rejected", "learning_feedback"}.issubset(event_types)


def test_promise_radar_accuracy_fixture_audit_passes():
    report = audit_accuracy_set(target_real_cases=100)

    assert report["passed"] is True
    assert report["case_count"] >= 172
    assert report["real_case_count"] >= 100
    assert report["errors"] == []
