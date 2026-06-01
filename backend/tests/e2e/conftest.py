"""
E2E 통합 테스트 공유 픽스처
SPEC-E2E-001: STT → DIA → MIN → SUM 전체 파이프라인 E2E 검증
"""

import io
import json
import struct
import wave
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 인메모리 Redis mock - 실제 저장/조회 동작 시뮬레이션
# ---------------------------------------------------------------------------


class InMemoryRedis:
    """인메모리 Redis mock - 실제 저장/조회 동작"""

    def __init__(self) -> None:
        # 문자열 키-값 저장소
        self._storage: dict[str, str] = {}
        # Set 자료구조 저장소
        self._sets: dict[str, set] = {}

    async def get(self, key: str) -> str | None:
        """키에 해당하는 값 반환 (없으면 None)"""
        return self._storage.get(key)

    async def set(self, key: str, value: str) -> bool:
        """키-값 저장"""
        self._storage[key] = value
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        """키-값 저장 (TTL 무시 - 인메모리에서는 만료 없음)"""
        self._storage[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        """키 삭제, 삭제된 키 수 반환"""
        count = 0
        for key in keys:
            if key in self._storage:
                del self._storage[key]
                count += 1
        return count

    async def scard(self, key: str) -> int:
        """Set의 원소 수 반환"""
        return len(self._sets.get(key, set()))

    async def sadd(self, key: str, *members: str) -> int:
        """Set에 원소 추가, 추가된 수 반환"""
        if key not in self._sets:
            self._sets[key] = set()
        added = 0
        for m in members:
            if m not in self._sets[key]:
                self._sets[key].add(m)
                added += 1
        return added

    async def srem(self, key: str, *members: str) -> int:
        """Set에서 원소 제거, 제거된 수 반환"""
        removed = 0
        if key in self._sets:
            for m in members:
                if m in self._sets[key]:
                    self._sets[key].discard(m)
                    removed += 1
        return removed

    async def incr(self, key: str) -> int:
        """정수 값 1 증가"""
        val = int(self._storage.get(key, "0")) + 1
        self._storage[key] = str(val)
        return val

    async def decr(self, key: str) -> int:
        """정수 값 1 감소"""
        val = int(self._storage.get(key, "0")) - 1
        self._storage[key] = str(val)
        return val

    async def ping(self) -> bool:
        """연결 확인"""
        return True

    async def exists(self, *keys: str) -> int:
        """키 존재 여부 확인, 존재하는 키 수 반환"""
        return sum(1 for k in keys if k in self._storage)


# ---------------------------------------------------------------------------
# E2E 테스트용 mock 데이터 상수
# ---------------------------------------------------------------------------

# STT 결과 mock 데이터 - Redis 저장 JSON 형식과 일치
MOCK_STT_RESULT = {
    "task_id": "stt-task-id-placeholder",
    "status": "completed",
    "language": "ko",
    "duration": 120.5,
    "model": "mlx-community/whisper-large-v3-turbo",
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 4.2,
            "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
            "confidence": 0.92,
        },
        {
            "id": 1,
            "start": 4.5,
            "end": 8.1,
            "text": "네, 시작하죠. 오늘 안건은 무엇인가요?",
            "confidence": 0.88,
        },
    ],
    "metadata": {
        "file_name": "meeting.wav",
        "file_size_bytes": 100000,
        "sample_rate": 16000,
        "processing_time_seconds": 5.2,
    },
    "created_at": "2024-01-15T09:00:00+00:00",
    "completed_at": "2024-01-15T09:00:05+00:00",
}

# DIA 결과 mock 데이터 - Redis 저장 JSON 형식과 일치
MOCK_DIA_RESULT = {
    "task_id": "dia-task-id-placeholder",
    "stt_task_id": "stt-task-id-placeholder",
    "status": "completed",
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 4.2,
            "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
            "confidence": 0.92,
            "speaker_id": "SPEAKER_00",
            "speaker_confidence": 0.95,
        },
        {
            "id": 1,
            "start": 4.5,
            "end": 8.1,
            "text": "네, 시작하죠. 오늘 안건은 무엇인가요?",
            "confidence": 0.88,
            "speaker_id": "SPEAKER_01",
            "speaker_confidence": 0.91,
        },
    ],
    "speakers": [
        {
            "speaker_id": "SPEAKER_00",
            "total_speaking_time": 4.2,
            "segment_count": 1,
        },
        {
            "speaker_id": "SPEAKER_01",
            "total_speaking_time": 3.6,
            "segment_count": 1,
        },
    ],
    "num_speakers": 2,
    "created_at": "2024-01-15T09:00:10+00:00",
    "completed_at": "2024-01-15T09:00:15+00:00",
}

# MIN 결과 mock 데이터 - Redis 저장 JSON 형식과 일치
MOCK_MIN_RESULT = {
    "task_id": "min-task-id-placeholder",
    "diarization_task_id": "dia-task-id-placeholder",
    "status": "completed",
    "segments": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "화자 1",
            "text": "안녕하세요, 오늘 회의를 시작하겠습니다.",
            "start": 0.0,
            "end": 4.2,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "화자 2",
            "text": "네, 시작하죠. 오늘 안건은 무엇인가요?",
            "start": 4.5,
            "end": 8.1,
        },
    ],
    "speakers": [
        {
            "speaker_id": "SPEAKER_00",
            "speaker_name": "화자 1",
            "total_speaking_time": 4.2,
            "segment_count": 1,
            "speaking_ratio": 53.8,
        },
        {
            "speaker_id": "SPEAKER_01",
            "speaker_name": "화자 2",
            "total_speaking_time": 3.6,
            "segment_count": 1,
            "speaking_ratio": 46.2,
        },
    ],
    "total_duration": 7.8,
    "total_speakers": 2,
    "markdown": "# 회의록\n\n**화자 1**: 안녕하세요...",
    "created_at": "2024-01-15T09:00:20+00:00",
    "completed_at": "2024-01-15T09:00:25+00:00",
}

# SUM 결과 mock 데이터 - Redis 저장 JSON 형식과 일치
MOCK_SUM_RESULT = {
    "task_id": "sum-task-id-placeholder",
    "minutes_task_id": "min-task-id-placeholder",
    "status": "completed",
    "summary_text": "오늘 회의에서는 팀 업무 진행 상황을 논의했습니다.",
    "action_items": [
        {
            "assignee": "화자 1",
            "task": "다음 회의 일정 조율",
            "deadline": "2024-01-22",
            "priority": "high",
        }
    ],
    "key_decisions": ["다음 스프린트 목표 확정", "예산 계획 승인"],
    "next_steps": ["팀 리뷰 미팅 예약", "문서 업데이트"],
    "tokens_used": {"input_tokens": 300, "output_tokens": 150},
    "generation_time_seconds": 3.2,
    "created_at": "2024-01-15T09:00:30+00:00",
    "completed_at": "2024-01-15T09:00:33+00:00",
}


# ---------------------------------------------------------------------------
# 헬퍼 함수
# ---------------------------------------------------------------------------


def make_test_wav(duration_seconds: int = 1, sample_rate: int = 16000) -> bytes:
    """테스트용 최소 WAV 파일 바이트 생성"""
    num_samples = sample_rate * duration_seconds
    # 무음 PCM 데이터 생성
    data = struct.pack(f"<{num_samples}h", *([0] * num_samples))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(data)
    buf.seek(0)
    return buf.read()


async def inject_result(
    redis: InMemoryRedis,
    status_key: str,
    result_key: str,
    task_id: str,
    result_dict: dict,
) -> None:
    """
    파이프라인 단계별 결과를 Redis에 직접 주입하는 헬퍼
    실제 Celery 워커 없이 결과를 시뮬레이션
    """
    # task_id를 결과 데이터에 반영
    result_with_id = {**result_dict, "task_id": task_id}

    # 상태를 completed로 업데이트
    status_data = {
        "task_id": task_id,
        "status": "completed",
        "progress": 1.0,
        "created_at": result_dict.get("created_at", "2024-01-15T09:00:00+00:00"),
        "updated_at": result_dict.get("completed_at", "2024-01-15T09:00:05+00:00"),
    }

    # stt_task_id 또는 diarization_task_id 등 추가 필드 포함
    for key in ("stt_task_id", "diarization_task_id", "minutes_task_id"):
        if key in result_dict:
            status_data[key] = result_dict[key]

    await redis.setex(status_key, 86400, json.dumps(status_data))
    await redis.setex(result_key, 86400, json.dumps(result_with_id))


# ---------------------------------------------------------------------------
# E2E 픽스처
# ---------------------------------------------------------------------------


@pytest.fixture
def e2e_redis() -> InMemoryRedis:
    """E2E 테스트용 InMemoryRedis 인스턴스"""
    return InMemoryRedis()


@pytest.fixture
def e2e_client(e2e_redis: InMemoryRedis, tmp_path):
    """
    E2E 테스트용 FastAPI TestClient
    - InMemoryRedis를 dependency_overrides로 주입 (실제 저장/조회 동작)
    - 4개 Celery task.delay() mock (즉시 task_id 반환)
    - WhisperEngine, DiarizationEngine mock (모델 로드 방지)
    - settings mock (임시 디렉토리 사용)
    """
    from fastapi.testclient import TestClient

    from backend.app.config import Settings
    from backend.app.dependencies import get_redis_client
    from backend.app.main import app
    from backend.app.middleware.auth import verify_api_key

    # 임시 디렉토리 설정
    test_settings = MagicMock(spec=Settings)
    test_settings.max_file_size_bytes = 500 * 1024 * 1024
    test_settings.max_file_size_mb = 500
    test_settings.max_duration_seconds = 4 * 3600
    test_settings.max_duration_hours = 4
    test_settings.max_concurrent_jobs = 3
    test_settings.max_concurrent_diarizations = 2
    test_settings.max_concurrent_minutes = 3
    test_settings.max_concurrent_summaries = 2
    test_settings.temp_dir = tmp_path / "temp"
    test_settings.results_dir = tmp_path / "results"
    test_settings.cache_ttl_seconds = 604800
    test_settings.diarization_result_ttl = 604800
    test_settings.minutes_result_ttl = 604800
    test_settings.summary_result_ttl = 604800
    test_settings.whisper_model = "mlx-community/whisper-large-v3-turbo"
    test_settings.whisper_language = "ko"
    test_settings.chunk_duration_ms = 30 * 60 * 1000
    test_settings.chunk_overlap_ms = 5000
    test_settings.memory_warning_threshold_mb = 19660
    test_settings.temp_dir.mkdir(parents=True, exist_ok=True)
    test_settings.results_dir.mkdir(parents=True, exist_ok=True)

    # InMemoryRedis를 의존성 오버라이드로 주입
    async def override_redis():
        return e2e_redis

    app.dependency_overrides[get_redis_client] = override_redis

    # REQ-SEC-004: 테스트에서 API Key 검증 건너뜀
    async def override_verify_api_key():
        return "test-bypass"

    app.dependency_overrides[verify_api_key] = override_verify_api_key

    # STT: transcription_task.delay mock
    mock_stt_result = MagicMock()
    mock_stt_result.id = "mock-stt-celery-id"

    # DIA: diarization_celery_task.delay mock
    mock_dia_result = MagicMock()
    mock_dia_result.id = "mock-dia-celery-id"

    # MIN: minutes_celery_task.delay mock
    mock_min_result = MagicMock()
    mock_min_result.id = "mock-min-celery-id"

    # SUM: summary_celery_task.delay mock
    mock_sum_result = MagicMock()
    mock_sum_result.id = "mock-sum-celery-id"

    # WhisperEngine mock (lifespan 중 모델 로드 방지)
    with patch("backend.app.main.WhisperEngine") as mock_whisper_cls:
        mock_whisper_inst = MagicMock()
        mock_whisper_inst.is_loaded = True
        mock_whisper_inst.load.return_value = None
        mock_whisper_cls.get_instance.return_value = mock_whisper_inst

        # DiarizationEngine mock (API 핸들러 내 모델 로드 방지)
        with patch(
            "backend.app.api.v1.transcription.settings",
            test_settings,
        ):
            with patch(
                "backend.pipeline.audio_processor.get_audio_duration_seconds",
                return_value=60.0,
            ):
                # 4개 Celery task delay 모두 mock
                with patch(
                    "backend.workers.tasks.transcription_task.transcription_task.delay"
                ) as mock_stt_delay:
                    mock_stt_delay.return_value = mock_stt_result

                    with patch(
                        "backend.workers.tasks.diarization_task.diarization_celery_task.delay"
                    ) as mock_dia_delay:
                        mock_dia_delay.return_value = mock_dia_result

                        with patch(
                            "backend.workers.tasks.diarization_task.diarization_celery_task.apply_async"
                        ) as mock_dia_apply:
                            mock_dia_apply.return_value = mock_dia_result

                            with patch(
                                "backend.workers.tasks.minutes_task.minutes_celery_task.delay"
                            ) as mock_min_delay:
                                mock_min_delay.return_value = mock_min_result

                                with patch(
                                    "backend.workers.tasks.summary_task.summary_celery_task.delay"
                                ) as mock_sum_delay:
                                    mock_sum_delay.return_value = mock_sum_result

                                    yield TestClient(app, raise_server_exceptions=True)

    app.dependency_overrides.clear()
