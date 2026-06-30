from datetime import datetime, timedelta

from backend.db.models import TaskResult
from backend.services.promise_radar_service import PromiseRadarService


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
