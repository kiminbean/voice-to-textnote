"""
요약 Celery 태스크 단위 테스트 (RED phase)
REQ-SUM-006: POST /api/v1/summaries → Celery 비동기 처리
REQ-SUM-007: Redis에서 회의록 결과 조회 (task:min:result:{minutes_task_id})
REQ-SUM-008: 최대 2개 동시 작업 제한
REQ-SUM-009: 최대 2회 재시도, default_retry_delay=30s
REQ-SUM-010: 회의록 결과 없음 → 즉시 실패 (재시도 없음)
REQ-SUM-011: ANTHROPIC_API_KEY 빈 값 → 즉시 실패 (재시도 없음)
"""

import json
import uuid
from unittest.mock import MagicMock, patch

from backend.workers.tasks.summary_task import _get_redis

# ---------------------------------------------------------------------------
# 테스트 헬퍼 / 모의 데이터
# ---------------------------------------------------------------------------

# 정상 회의록 결과 (Redis에서 조회되는 형태)
MOCK_MIN_RESULT = {
    "task_id": str(uuid.uuid4()),
    "diarization_task_id": str(uuid.uuid4()),
    "status": "completed",
    "segments": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "text": "안녕하세요.",
            "start": 0.0,
            "end": 5.0,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "Speaker 2",
            "text": "반갑습니다.",
            "start": 5.0,
            "end": 10.0,
        },
    ],
    "speakers": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "Speaker 1",
            "total_speaking_time": 5.0,
            "segment_count": 1,
            "speaking_ratio": 50.0,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "Speaker 2",
            "total_speaking_time": 5.0,
            "segment_count": 1,
            "speaking_ratio": 50.0,
        },
    ],
    "total_duration": 10.0,
    "total_speakers": 2,
    "markdown": None,
    "created_at": "2025-01-01T00:00:00+00:00",
    "completed_at": "2025-01-01T00:00:10+00:00",
}


def _make_mock_redis(active_count: int = 0) -> MagicMock:
    """Redis 동기 클라이언트 mock 생성"""
    mock = MagicMock()
    mock.get.return_value = None
    mock.set.return_value = True
    mock.setex.return_value = True
    mock.delete.return_value = 1
    mock.scard.return_value = active_count
    mock.sadd.return_value = 1
    mock.srem.return_value = 1
    # _get_active_sum_count() uses pipeline() → zremrangebyscore, zcard, execute
    mock_pipe = MagicMock()
    mock_pipe.zremrangebyscore.return_value = 0
    mock_pipe.zcard.return_value = active_count
    mock_pipe.zadd.return_value = 1
    mock_pipe.zrem.return_value = 1
    mock_pipe.execute.return_value = [0, active_count]
    mock.pipeline.return_value = mock_pipe
    return mock


def _make_mock_summary_generator(summary_text: str = "테스트 요약") -> MagicMock:
    """SummaryGenerator mock 생성"""
    from backend.schemas.summary import SummaryResult

    mock_result = SummaryResult(
        summary_text=summary_text,
        action_items=[],
        key_decisions=["결정 1"],
        next_steps=["다음 단계 1"],
    )

    mock_gen = MagicMock()
    mock_gen.return_value.generate_summary.return_value = mock_result
    return mock_gen


# ---------------------------------------------------------------------------
# 정상 처리 흐름 테스트 (Happy Path)
# ---------------------------------------------------------------------------


class TestSummaryTaskHappyPath:
    """정상 요약 생성 흐름 테스트"""

    def test_task_returns_completed_result(self):
        """회의록 결과 존재 + API 키 유효 → completed 결과 반환"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis(active_count=0)
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(
                        task_id=task_id,
                        minutes_task_id=min_task_id,
                        max_tokens=2000,
                    )

        assert result["status"] == "completed"
        assert result["task_id"] == task_id

    def test_task_result_has_summary_text(self):
        """완료 결과에 summary_text 포함"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = _make_mock_summary_generator("이것은 테스트 요약입니다.")

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(
                        task_id=task_id,
                        minutes_task_id=min_task_id,
                    )

        assert "summary_text" in result
        assert result["summary_text"] == "이것은 테스트 요약입니다."

    def test_task_caches_result_in_redis(self):
        """완료 후 결과가 Redis에 캐싱됨 (REQ-SUM-014: 24h TTL)"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    summary_task(task_id=task_id, minutes_task_id=min_task_id)

        # Redis setex 호출 확인 (캐싱)
        assert mock_redis.setex.called

    def test_task_result_has_required_fields(self):
        """완료 결과에 필수 필드 포함"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        required_fields = ("task_id", "minutes_task_id", "status", "summary_text")
        for field in required_fields:
            assert field in result, f"결과에 '{field}' 필드 누락"


# ---------------------------------------------------------------------------
# 오류 조건 테스트
# ---------------------------------------------------------------------------


class TestSummaryTaskErrors:
    """오류 조건 처리 테스트"""

    def test_minutes_result_not_found_returns_failed(self):
        """회의록 결과 없음 → failed 반환 (REQ-SUM-010: 재시도 없음)"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None  # 회의록 결과 없음

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000

                result = summary_task(
                    task_id=task_id,
                    minutes_task_id=min_task_id,
                )

        assert result["status"] == "failed"
        assert "error" in result

    def test_minutes_result_not_found_error_message(self):
        """회의록 결과 없음 → error 메시지에 404 의미 포함"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.return_value = None

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000

                result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        # 에러 메시지에 minutes_task_id가 포함되어야 함
        assert min_task_id in result["error"] or "찾을 수 없" in result["error"]

    def test_empty_api_key_returns_failed_immediately(self):
        """ANTHROPIC_API_KEY 빈 값 → 즉시 실패, 재시도 없음 (REQ-SUM-011)"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = ""  # 빈 API 키
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000

                result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        assert result["status"] == "failed"
        assert "OPENAI_API_KEY" in result["error"]

    def test_max_concurrent_limit_exceeded_returns_rejected(self):
        """동시 실행 2개 한도 초과 → rejected 반환 (REQ-SUM-008)"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        # 이미 2개 활성 작업 중
        mock_redis = _make_mock_redis(active_count=2)
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000

                result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        assert result["status"] in ("failed", "rejected")

    def test_api_exception_returns_failed(self):
        """API 호출 예외 → failed 상태"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = MagicMock()
        mock_gen_cls.return_value.generate_summary.side_effect = Exception("API 연결 실패")

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        assert result["status"] == "failed"

    def test_failed_minutes_result_propagates_upstream_error(self):
        """선행 회의록 작업 실패 시 원인 메시지를 보존"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())
        failed_minutes = {
            "task_id": min_task_id,
            "status": "failed",
            "error_message": "화자 분리 실패",
        }

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(failed_minutes) if f"min:result:{min_task_id}" in key else None
        )

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "gpt-4o-mini"

                result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        assert result["status"] == "failed"
        assert "화자 분리 실패" in result["error_message"]

    def test_valid_template_structure_is_passed_to_generator(self):
        """template_id가 있으면 Redis 양식 구조를 요약기에 전달"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())
        template_id = str(uuid.uuid4())
        template_structure = {"sections": [{"title": "결정사항", "prompt": "요약"}]}

        mock_redis = _make_mock_redis()

        def get_side_effect(key):
            if f"min:result:{min_task_id}" in key:
                return json.dumps(MOCK_MIN_RESULT)
            if key == f"template:{template_id}":
                return json.dumps({"structure": template_structure})
            return None

        mock_redis.get.side_effect = get_side_effect
        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "gpt-4o-mini"
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(
                        task_id=task_id,
                        minutes_task_id=min_task_id,
                        template_id=template_id,
                    )

        assert result["template_structure"] == template_structure
        generate_call = mock_gen_cls.return_value.generate_summary.call_args.kwargs
        assert generate_call["template_structure"] == template_structure

    def test_invalid_template_metadata_falls_back_to_default_summary(self):
        """양식 메타데이터가 깨져도 기본 요약으로 진행"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())
        template_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT)
            if f"min:result:{min_task_id}" in key
            else "{not-json"
            if key == f"template:{template_id}"
            else None
        )
        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "gpt-4o-mini"
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(
                        task_id=task_id,
                        minutes_task_id=min_task_id,
                        template_id=template_id,
                    )

        assert result["status"] == "completed"
        assert result["template_structure"] is None


# ---------------------------------------------------------------------------
# Redis 클라이언트 싱글톤 테스트
# ---------------------------------------------------------------------------


class TestSummaryTaskRedisClient:
    """_get_redis() 싱글톤 동작 테스트"""

    def test_get_redis_creates_client_when_none(self):
        """_get_redis()가 get_worker_redis()를 호출해 클라이언트 반환"""
        mock_client = MagicMock()
        with patch("backend.workers.tasks.summary_task.get_worker_redis", return_value=mock_client):
            result = _get_redis()
        assert result is mock_client

    def test_get_redis_returns_cached_client(self):
        """_get_redis()가 항상 get_worker_redis() 결과를 반환"""
        mock_client = MagicMock()
        with patch("backend.workers.tasks.summary_task.get_worker_redis", return_value=mock_client):
            result = _get_redis()
        assert result is mock_client


# ---------------------------------------------------------------------------
# 상태 전환 테스트
# ---------------------------------------------------------------------------


class TestSummaryTaskStatusTransitions:
    """상태 전환: pending → processing → completed/failed"""

    def test_final_status_is_completed_on_success(self):
        """성공 시 최종 status=completed"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    result = summary_task(task_id=task_id, minutes_task_id=min_task_id)

        assert result["status"] == "completed"

    def test_status_updated_during_processing(self):
        """처리 중 Redis status 업데이트 발생"""
        from backend.workers.tasks.summary_task import summary_task

        task_id = str(uuid.uuid4())
        min_task_id = str(uuid.uuid4())

        status_updates = []

        mock_redis = _make_mock_redis()
        mock_redis.get.side_effect = lambda key: (
            json.dumps(MOCK_MIN_RESULT) if f"min:result:{min_task_id}" in key else None
        )

        def track_setex(key, ttl, data):
            if "status" in key:
                try:
                    status_updates.append(json.loads(data))
                except Exception:
                    pass
            return True

        mock_redis.setex.side_effect = track_setex

        mock_gen_cls = _make_mock_summary_generator()

        with patch("backend.workers.tasks.summary_task._get_redis", return_value=mock_redis):
            with patch("backend.workers.tasks.summary_task.settings") as mock_settings:
                mock_settings.summary_result_ttl = 86400
                mock_settings.max_concurrent_summaries = 2
                mock_settings.openai_api_key = "sk-test-key"
                mock_settings.summary_model = "claude-sonnet-4-20250514"
                mock_settings.summary_max_tokens = 2000
                with patch("backend.workers.tasks.summary_task.SummaryGenerator", mock_gen_cls):
                    summary_task(task_id=task_id, minutes_task_id=min_task_id)

        statuses = [u.get("status") for u in status_updates if "status" in u]
        assert any(s in ("processing", "completed") for s in statuses)


class TestSummaryCeleryWrapper:
    """summary_celery_task wrapper 분기 검증"""

    def test_wrapper_returns_failed_for_missing_minutes(self):
        from backend.workers.tasks.summary_task import summary_celery_task

        with patch(
            "backend.workers.tasks.summary_task.summary_task",
            side_effect=FileNotFoundError("missing minutes"),
        ):
            result = summary_celery_task.run("task-id", "minutes-id")

        assert result == {
            "task_id": "task-id",
            "status": "failed",
            "error": "missing minutes",
        }

    def test_wrapper_returns_failed_after_max_retries(self):
        from backend.workers.tasks.summary_task import summary_celery_task

        with patch(
            "backend.workers.tasks.summary_task.summary_task",
            side_effect=RuntimeError("temporary outage"),
        ), patch.object(
            summary_celery_task,
            "retry",
            side_effect=summary_celery_task.MaxRetriesExceededError(),
        ) as retry:
            result = summary_celery_task.run("task-id", "minutes-id")

        retry.assert_called_once_with(exc=retry.call_args.kwargs["exc"], countdown=30)
        assert result["status"] == "failed"
        assert result["error"] == "temporary outage"
