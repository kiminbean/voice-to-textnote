"""
Celery 앱 설정
브로커: Redis, 결과 백엔드: Redis
"""

from celery import Celery
from celery.schedules import crontab

from backend.app.config import settings

celery_app = Celery(
    "voice_to_textnote",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "backend.workers.tasks.transcription_task",
        "backend.workers.tasks.diarization_task",
        "backend.workers.tasks.minutes_task",
        "backend.workers.tasks.summary_task",
        # SPEC-SENTIMENT-001: 감정 분석 태스크 등록 (REQ-SEN-001)
        # 누락 시 워커가 sentiment_celery_task를 발견하지 못해 작업이 pending에 머무름
        "backend.workers.tasks.sentiment_task",
        "backend.workers.tasks.mind_map_task",
        "backend.workers.tasks.cleanup_task",
    ],
)

celery_app.conf.update(
    # 직렬화
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 타임존
    timezone="Asia/Seoul",
    enable_utc=True,
    # 재시도 정책 (REQ-STT: 최대 3회 재시도, 지수 백오프)
    task_max_retries=3,
    task_retry_backoff=True,
    task_retry_backoff_max=300,  # 최대 5분 대기
    # 작업 결과 TTL (24시간)
    result_expires=86400,
    # 동시 처리 제한 - 워커 실행 시 --concurrency=3 으로 제어
    # 여기서는 기본값 설정만
    worker_prefetch_multiplier=1,  # 1개씩 가져와서 메모리 효율 보장
    # REQ-PERF-002: 장시간 작업의 중복 실행 방지
    # 기본값 3600초(1시간) → 7200초(2시간)로 증가
    # soft_time_limit=3600 작업이 visibility_timeout 내에서 완료될 수 있도록 보장
    broker_transport_options={"visibility_timeout": 7200},
    # 모니터링
    task_send_sent_event=True,
    task_track_started=True,
)


# REQ-RET-006: 매일 03:00 데이터 정리 스케줄
celery_app.conf.beat_schedule = {
    "cleanup-expired-data": {
        "task": "cleanup_expired_data",
        "schedule": crontab(hour=3, minute=0),
    },
}
