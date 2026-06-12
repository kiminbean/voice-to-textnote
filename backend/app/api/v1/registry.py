"""
라우터 등록 레지스트리 — 등록 순서와 인증 정책의 SSOT(Single Source of Truth).

# @MX:ANCHOR: 라우터 등록 순서와 API Key 인증 정책의 단일 진실 공급원
# @MX:REASON: main.py의 create_app()이 이 목록을 순서대로 소비한다.
#             순서 변경은 URL 충돌(batch → transcription 참조)이나 인증 회귀를 유발할 수 있다.
# @MX:SPEC: SPEC-REFACTOR-001 (REQ-RM-C2)

ROUTER_REGISTRY 구조:
  (router, requires_api_key)
  - requires_api_key=True  → dependencies=[Depends(verify_api_key)] 적용
  - requires_api_key=False → router-level 의존성 없음 (공개 엔드포인트이거나 JWT를 직접 처리)

주의: 아래 목록의 순서는 절대 임의로 변경하지 말 것.
  - batch는 반드시 transcription보다 먼저 등록되어야 한다.
    이유: /transcriptions/{task_id} 경로와 /batch/... 경로 충돌 방지.
"""

from fastapi import APIRouter

from backend.app.api.v1.admin import (
    admin,
    calendar,
    export,
    health,
    history,
    templates,
)
from backend.app.api.v1.templates import enhanced
from backend.app.api.v1.analytics import (
    advanced_search,
    dashboard,
    enhanced_statistics,
    search,
    sentiment,
    statistics,
    vocabulary,
)
from backend.app.api.v1.audio import (
    audio,
    audio_analysis,
    audio_preprocess,
    enhanced_preprocess,
    qa,
    quality_assessment,
)
from backend.app.api.v1.auth import (
    auth,
    devices,
)
from backend.app.api.v1.collaboration import (
    bookmarks,
    meetings,
    speakers,
    teams,
    versions,
    webhooks,
)
from backend.app.api.v1.minutes import (
    action_items,
    action_items_crud,
    keywords,
    minutes,
    summary,
    tags,
)
from backend.app.api.v1.transcription import (
    batch,
    diarization,
    stream,
)
from backend.app.api.v1.transcription import (
    transcription as transcription_module,
)

# 각 튜플: (APIRouter, requires_api_key)
# 총 35개 라우터 — 25개 True, 10개 False
ROUTER_REGISTRY: list[tuple[APIRouter, bool]] = [
    # ── 핵심 STT/처리 파이프라인 (API Key 필수) ──────────────────────────────────
    # 주의: batch는 transcription 보다 반드시 먼저 와야 함 (경로 충돌 방지)
    (batch.router, True),
    (transcription_module.router, True),
    (diarization.router, True),
    (minutes.router, True),
    (summary.router, True),
    # ── 공개 엔드포인트 (API Key 불필요) ────────────────────────────────────────
    (health.router, False),
    # ── 스트리밍 / 이력 (API Key 필수) ──────────────────────────────────────────
    (stream.router, True),  # REQ-SSE-001: 태스크 상태 실시간 스트리밍
    (history.router, True),  # SPEC-HISTORY-001: 작업 이력 조회/삭제
    # ── 관리 / 설정 (API Key 필수) ──────────────────────────────────────────────
    (admin.router, True),  # SPEC-RETENTION-001
    (enhanced.router, True),  # Enhanced template system
    (templates.router, True),  # REQ-TMPL-001/003
    (search.router, True),  # SPEC-SEARCH-001
    (export.router, True),  # SPEC-EXPORT-001
    (statistics.router, True),  # SPEC-STATS-001
    (dashboard.router, True),  # SPEC-STATS-002
    (enhanced_statistics.router, True),  # SPEC-ENHANCED-STATS-001
    (advanced_search.router, True),  # SPEC-ADVANCED-SEARCH-001
    # ── 확장 오디오 처리 (API Key 필수) ──────────────────────────────────────────
    (enhanced_preprocess.router, True),  # 고급 오디오 전처리 (AI 기반)
    # ── 인증 / 디바이스 / 팀 협업 (공개, JWT를 엔드포인트에서 직접 처리) ──────────
    (auth.router, False),  # SPEC-TEAM-001
    (devices.router, False),  # SPEC-MOBILE-001
    (teams.router, False),  # SPEC-TEAM-001
    (meetings.router, False),  # SPEC-TEAM-001 REQ-TEAM-005
    (bookmarks.router, False),  # SPEC-BOOKMARK-001
    (speakers.router, False),  # SPEC-SPEAKER-001
    (webhooks.router, False),  # SPEC-WEBHOOK-001
    (versions.router, False),  # SPEC-VERSION-001
    # ── AI 분석 (API Key 필수) ──────────────────────────────────────────────────
    (sentiment.router, True),
    (tags.router, True),  # SPEC-TAG-001
    (keywords.router, True),  # SPEC-KEYWORD-001
    (action_items.router, True),  # SPEC-ACTION-001
    (action_items_crud.router, True),  # SPEC-ACTION-001: CRUD management
    (audio_analysis.router, True),  # SPEC-AUDIO-ANALYSIS-001
    (audio_preprocess.router, True),  # SPEC-AUDIO-PREP-001
    (quality_assessment.router, True),  # SPEC-QUALITY-001
    (calendar.router, True),  # SPEC-CAL-001
    (vocabulary.router, True),  # REQ-VOCAB-001
    # ── 오디오 파일 서빙 / QA (혼합 인증) ───────────────────────────────────────
    (audio.router, False),  # 공개 엔드포인트
    (enhanced_preprocess.router, True),  # 고급 오디오 전처리
    (qa.router, True),
]
