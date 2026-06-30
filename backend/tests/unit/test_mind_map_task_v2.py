"""
마인드맵 생성 Celery 태스크 추가 테스트 (커버리지 보완)
기존 test_mind_map_task.py에서 커버하지 않는 경로 테스트
"""

import json
import uuid
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# 테스트 헬퍼
# ---------------------------------------------------------------------------


def _make_mock_redis(summary_task_id: str, summary_result: dict | None = None):
    """Redis mock 생성"""
    mock = MagicMock()
    mock.get.side_effect = lambda key: (
        json.dumps(summary_result)
        if summary_result and key == f"task:sum:result:{summary_task_id}"
        else None
    )
    mock.setex.return_value = True
    mock.publish.return_value = 1
    return mock


def _make_mock_generator():
    """MindMapGenerator mock 생성"""
    from backend.schemas.summary import MindMapEdge, MindMapNode

    root = MindMapNode(
        id="root",
        title="제품 출시",
        summary="출시 결정과 후속 QA",
        source_refs=["summary_text"],
    )
    edges = [MindMapEdge(source="root", target="qa", relation="leads_to")]

    mock_cls = MagicMock()
    mock_cls.return_value.generate_mind_map.return_value = (root, edges)
    return mock_cls


def _default_patches(mock_redis, mock_settings):
    """공통 컨텍스트 매니저 생성 (설정 + Redis + 이벤트)"""
    from contextlib import ExitStack

    stack = ExitStack()
    stack.enter_context(
        patch("backend.workers.tasks.mind_map_task._get_redis", return_value=mock_redis)
    )
    stack.enter_context(patch("backend.workers.tasks.mind_map_task.settings", mock_settings))
    stack.enter_context(patch("backend.workers.tasks.mind_map_task.publish_task_event_sync"))
    return stack


# ---------------------------------------------------------------------------
# LLM 키 누락 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskZAIKeyMissing:
    """LLM API 키 설정 관련 테스트"""

    def test_fails_when_llm_api_key_not_configured(self):
        """LLM API 키 없음 → failed 결과 반환"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())
        mock_redis = _make_mock_redis(summary_task_id, None)

        mock_settings = MagicMock()
        mock_settings.llm_api_key = None  # 키 없음
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with _default_patches(mock_redis, mock_settings):
            result = mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert result["status"] == "failed"
        assert "LLM API key" in result["error_message"]


# ---------------------------------------------------------------------------
# 상태 보존 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskStatusPreservation:
    """created_at 보존 로직 테스트"""

    def test_preserves_created_at_on_status_update(self):
        """상태 업데이트 시 기존 created_at 보존됨"""
        from backend.schemas.transcription import TaskStatus
        from backend.workers.tasks.mind_map_task import _update_mind_map_status

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        existing_data = {
            "task_id": task_id,
            "summary_task_id": summary_task_id,
            "status": "processing",
            "progress": 0.1,
            "created_at": "2024-01-01T00:00:00+00:00",
        }

        mock_redis = MagicMock()
        # status 키 조회 시 기존 데이터 반환
        mock_redis.get.side_effect = lambda key: (
            json.dumps(existing_data) if "status" in key else None
        )
        mock_redis.setex.return_value = True

        mock_settings = MagicMock()
        mock_settings.summary_result_ttl = 86400

        with (
            patch("backend.workers.tasks.mind_map_task._get_redis", return_value=mock_redis),
            patch("backend.workers.tasks.mind_map_task.settings", mock_settings),
            patch("backend.workers.tasks.mind_map_task.publish_task_event_sync"),
        ):
            _update_mind_map_status(
                task_id=task_id,
                summary_task_id=summary_task_id,
                status=TaskStatus.processing,
                progress=0.5,
            )

        # setex가 호출되었는지 확인
        assert mock_redis.setex.called
        # setex(key, ttl, data)에서 data는 세 번째 인자 (인덱스 2)
        call_args = mock_redis.setex.call_args
        status_key = call_args[0][0]
        assert f"task:mind:status:{task_id}" == status_key

        # created_at 보존 확인
        saved_data = json.loads(call_args[0][2])
        assert saved_data["created_at"] == "2024-01-01T00:00:00+00:00"


# ---------------------------------------------------------------------------
# 업스트림 오류 처리 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskUpstreamErrors:
    """업스트림(요약 작업) 오류 전파 테스트"""

    def test_propagates_summary_not_found_error(self):
        """요약 결과 없음 → FileNotFoundError 발생 → failed 결과"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        mock_redis = _make_mock_redis(summary_task_id, None)
        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with _default_patches(mock_redis, mock_settings):
            result = mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert result["status"] == "failed"
        assert "요약 결과를 찾을 수 없습니다" in result["error_message"]

    def test_propagates_summary_failed_status_error(self):
        """요약 실패 상태 → RuntimeError 발생 → failed 결과"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        failed_summary = {
            "task_id": summary_task_id,
            "status": "failed",
            "error_message": "요약 생성 실패",
        }

        mock_redis = _make_mock_redis(summary_task_id, failed_summary)
        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with _default_patches(mock_redis, mock_settings):
            result = mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert result["status"] == "failed"
        assert (
            "완료 상태가 아닙니다" in result["error_message"]
            or "요약 작업이 완료되지 않았습니다" in result["error_message"]
        )

    def test_propagates_summary_error_message(self):
        """요약 결과에 error_message가 있으면 그 내용 전파"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        error_summary = {
            "task_id": summary_task_id,
            "status": "failed",
            "error_message": "요약 처리 중 오류 발생",
        }

        mock_redis = _make_mock_redis(summary_task_id, error_summary)
        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with _default_patches(mock_redis, mock_settings):
            result = mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert result["status"] == "failed"
        assert "요약 처리 중 오류 발생" in result["error_message"]


# ---------------------------------------------------------------------------
# 상태 업데이트 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskStatusUpdate:
    """상태 업데이트 테스트"""

    def test_update_status_with_task_type_field(self):
        """상태 업데이트 시 task_type='mind_map' 필드 포함"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        summary_result = {
            "task_id": summary_task_id,
            "status": "completed",
            "summary_text": "회의 요약",
        }

        mock_redis = _make_mock_redis(summary_task_id, summary_result)
        status_updates = []

        def track_setex(key, ttl, data):
            if "status" in key:
                status_updates.append(json.loads(data))
            return True

        mock_redis.setex.side_effect = track_setex

        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with (
            _default_patches(mock_redis, mock_settings),
            patch("backend.workers.tasks.mind_map_task.MindMapGenerator", _make_mock_generator()),
        ):
            mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        # processing 상태 업데이트 확인
        processing_status = next(
            (u for u in status_updates if u.get("status") == "processing"), None
        )
        assert processing_status is not None
        assert processing_status["task_type"] == "mind_map"


# ---------------------------------------------------------------------------
# 캐싱 TTL 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskCaching:
    """결과 캐싱 테스트"""

    def test_caches_result_with_ttl(self):
        """결과 Redis 캐싱 시 summary_result_ttl 사용"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        summary_result = {
            "task_id": summary_task_id,
            "status": "completed",
            "summary_text": "회의 요약",
        }

        mock_redis = _make_mock_redis(summary_task_id, summary_result)
        cache_calls = []

        def track_cache_setex(key, ttl, data):
            cache_calls.append({"key": key, "ttl": ttl})
            return True

        mock_redis.setex.side_effect = track_cache_setex

        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with (
            _default_patches(mock_redis, mock_settings),
            patch("backend.workers.tasks.mind_map_task.MindMapGenerator", _make_mock_generator()),
        ):
            mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert len(cache_calls) >= 2  # status + result
        result_cache = next((c for c in cache_calls if "result:" in c["key"]), None)
        assert result_cache is not None
        assert result_cache["ttl"] == 86400


# ---------------------------------------------------------------------------
# 일반 예외 처리 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskGenericException:
    """일반 예외 처리 테스트"""

    def test_generic_exception_returns_failed_result(self):
        """예상 발생 시 failed 결과 반환"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        summary_result = {
            "task_id": summary_task_id,
            "status": "completed",
            "summary_text": "회의 요약",
        }

        mock_redis = _make_mock_redis(summary_task_id, summary_result)
        mock_gen = MagicMock()
        mock_gen.return_value.generate_mind_map.side_effect = RuntimeError("AI 생성 오류")

        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with (
            _default_patches(mock_redis, mock_settings),
            patch("backend.workers.tasks.mind_map_task.MindMapGenerator", mock_gen),
        ):
            result = mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert result["status"] == "failed"
        assert "AI 생성 오류" in result["error_message"]


# ---------------------------------------------------------------------------
# Celery wrapper 테스트
# ---------------------------------------------------------------------------


class TestMindMapCeleryWrapper:
    """Celery 래퍼 테스트 - bind=True task의 self는 Celery가 자동 주입하므로 직접 호출"""

    def test_wrapper_propagates_file_not_found(self):
        """FileNotFoundError → 재시도 없이 failed 결과 반환"""
        from backend.workers.tasks.mind_map_task import mind_map_celery_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        with patch(
            "backend.workers.tasks.mind_map_task.mind_map_task",
            side_effect=FileNotFoundError("요약 결과 없음"),
        ):
            result = mind_map_celery_task(task_id, summary_task_id)

        assert result["status"] == "failed"
        assert "요약 결과 없음" in result["error"]

    def test_wrapper_retries_on_generic_exception(self):
        """일반 예외 시 self.retry() 호출 → MaxRetriesExceededError 시 failed 반환"""
        from backend.workers.tasks.mind_map_task import mind_map_celery_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        # Celery PromiseProxy의 실제 함수를 __func__로 추출하여 mock_self 주입
        raw_func = mind_map_celery_task.run.__func__

        mock_self = MagicMock()
        mock_self.MaxRetriesExceededError = type("MaxRetriesExceededError", (Exception,), {})
        mock_self.retry.side_effect = mock_self.MaxRetriesExceededError()

        with patch(
            "backend.workers.tasks.mind_map_task.mind_map_task",
            side_effect=RuntimeError("일시 오류"),
        ):
            result = raw_func(mock_self, task_id, summary_task_id)

        assert result["status"] == "failed"
        assert "일시 오류" in result["error"]
        assert mock_self.retry.called

    def test_wrapper_returns_failed_on_max_retries_exceeded(self):
        """최대 재시도 초과 시 failed 결과 반환"""
        from backend.workers.tasks.mind_map_task import mind_map_celery_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        raw_func = mind_map_celery_task.run.__func__

        mock_self = MagicMock()
        mock_self.MaxRetriesExceededError = type("MaxRetriesExceededError", (Exception,), {})
        mock_self.retry.side_effect = mock_self.MaxRetriesExceededError()

        with patch(
            "backend.workers.tasks.mind_map_task.mind_map_task",
            side_effect=RuntimeError("일시 오류"),
        ):
            result = raw_func(mock_self, task_id, summary_task_id)

        assert result["status"] == "failed"
        assert "일시 오류" in result["error"]


# ---------------------------------------------------------------------------
# 생성 시간 계산 테스트
# ---------------------------------------------------------------------------


class TestMindMapTaskGenerationTime:
    """생성 시간 계산 테스트"""

    def test_calculates_generation_time(self):
        """생성 시간을 초 단위로 계산"""
        from backend.workers.tasks.mind_map_task import mind_map_task

        task_id = str(uuid.uuid4())
        summary_task_id = str(uuid.uuid4())

        summary_result = {
            "task_id": summary_task_id,
            "status": "completed",
            "summary_text": "회의 요약",
        }

        mock_redis = _make_mock_redis(summary_task_id, summary_result)

        mock_settings = MagicMock()
        mock_settings.llm_api_key = "zai-test"
        mock_settings.summary_result_ttl = 86400
        mock_settings.summary_model = "gpt-4o"

        with (
            _default_patches(mock_redis, mock_settings),
            patch("backend.workers.tasks.mind_map_task.MindMapGenerator", _make_mock_generator()),
        ):
            result = mind_map_task(
                task_id=task_id,
                summary_task_id=summary_task_id,
                max_tokens=2048,
            )

        assert result["status"] == "completed"
        assert "generation_time_seconds" in result
        assert isinstance(result["generation_time_seconds"], float)
        assert result["generation_time_seconds"] >= 0
        assert "created_at" in result
        assert "completed_at" in result
