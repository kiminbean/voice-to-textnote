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
from backend.app.api.v1.analytics import (
    advanced_search,
    dashboard,
    efficiency,
    enhanced_statistics,
    related_meetings,
    search,
    sentiment,
    statistics,
    tone,
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
from backend.app.api.v1.audio.enhance import router as enhance_router
from backend.app.api.v1.auth import (
    auth,
    devices,
)
from backend.app.api.v1.collaboration import (
    bookmarks,
    collab,
    meetings,
    speaker_groups,
    speaker_statistics,
    speakers,
    teams,
    versions,
    webhooks,
)
from backend.app.api.v1.integrations import (
    obsidian,
)
from backend.app.api.v1.minutes import (
    action_items,
    action_items_crud,
    external_import,
    keywords,
    minutes,
    promise_radar,
    sales_contact_brief,
    sales_contacts,
    study_pack,
    summary,
    tags,
    translation,
)
from backend.app.api.v1.minutes.smart_summary import router as smart_summary_router
from backend.app.api.v1.transcription import (
    batch,
    diarization,
    stream,
)
from backend.app.api.v1.transcription import (
    transcription as transcription_module,
)

# 각 튜플: (APIRouter, requires_api_key)
# 총 47개 라우터. 동일 router 중복 등록 금지.
ROUTER_REGISTRY: list[tuple[APIRouter, bool]] = [
    # ── 핵심 STT/처리 파이프라인 (API Key 필수) ──────────────────────────────────
    # 주의: batch는 transcription 보다 반드시 먼저 와야 함 (경로 충돌 방지)
    (batch.router, True),
    (transcription_module.router, True),
    (diarization.router, True),
    (minutes.router, True),
    (external_import.router, True),  # SPEC-OWLL-IMPORT-001: external URL/text import
    (smart_summary_router, True),  # 다양한 모드로 스마트 요약 생성 (신규 기능)
    (summary.router, True),
    (sales_contact_brief.router, True),  # SPEC-OWLL-SALES-001: sales/contact follow-up brief
    (sales_contacts.router, True),  # SPEC-OWLL-SALES-002: sales/contact list surface
    (promise_radar.router, True),  # Cross-meeting promise/decision continuity radar
    (study_pack.router, True),  # SPEC-STUDY-001: transcript-grounded study packs
    (translation.router, True),  # SPEC-OWLL-TRANSLATION-001: persisted artifact translation
    # ── 공개 엔드포인트 (API Key 불필요) ────────────────────────────────────────
    (health.router, False),
    # ── 스트리밍 / 이력 (API Key 필수) ──────────────────────────────────────────
    (stream.router, True),  # REQ-SSE-001: 태스크 상태 실시간 스트리밍
    (history.router, True),  # SPEC-HISTORY-001: 작업 이력 조회/삭제
    # ── 관리 / 설정 (API Key 필수) ──────────────────────────────────────────────
    (admin.router, True),  # SPEC-RETENTION-001
    (templates.router, True),  # REQ-TMPL-001/003
    (search.router, True),  # SPEC-SEARCH-001
    (export.router, True),  # SPEC-EXPORT-001
    (statistics.router, True),  # SPEC-STATS-001
    (dashboard.router, True),  # SPEC-STATS-002
    (enhanced_statistics.router, True),  # SPEC-ENHANCED-STATS-001
    (efficiency.router, True),  # SPEC-EFFICIENCY-001: 회의 효율성 평가
    (advanced_search.router, True),  # SPEC-ADVANCED-SEARCH-001
    (related_meetings.router, True),  # SPEC-RELATED-001: 관련 회의 추천
    # ── 확장 오디오 처리 (API Key 필수) ──────────────────────────────────────────
    (enhanced_preprocess.router, True),  # 고급 오디오 전처리 (AI 기반)
    (enhance_router, True),  # AI 기반 오디오 향상 (신규 기능)
    # ── 인증 / 디바이스 / 팀 협업 (공개, JWT를 엔드포인트에서 직접 처리) ──────────
    (auth.router, False),  # SPEC-TEAM-001
    (devices.router, False),  # SPEC-MOBILE-001
    (teams.router, False),  # SPEC-TEAM-001
    (meetings.router, False),  # SPEC-TEAM-001 REQ-TEAM-005
    (bookmarks.router, False),  # SPEC-BOOKMARK-001
    (speaker_groups.router, False),  # 화자 그룁 관리
    (speaker_statistics.router, True),  # 화자별 통계
    (speakers.router, False),  # SPEC-SPEAKER-001
    (webhooks.router, False),  # SPEC-WEBHOOK-001
    (versions.router, False),  # SPEC-VERSION-001
    (collab.router, False),  # SPEC-COLLAB-001: WebSocket 실시간 공동 편집 (JWT in query param)
    # ── AI 분석 (API Key 필수) ──────────────────────────────────────────────────
    (sentiment.router, True),
    (tone.router, True),  # SPEC-TONE-001: 발화 톤/운율 분석 API
    (tags.router, True),  # SPEC-TAG-001
    (keywords.router, True),  # SPEC-KEYWORD-001
    (action_items.router, True),  # SPEC-ACTION-001
    (action_items_crud.router, True),  # SPEC-ACTION-001: CRUD management
    (audio_analysis.router, True),  # SPEC-AUDIO-ANALYSIS-001
    (audio_preprocess.router, True),  # SPEC-AUDIO-PREP-001
    (quality_assessment.router, True),  # SPEC-QUALITY-001
    (calendar.router, True),  # SPEC-CAL-001
    (vocabulary.router, True),  # REQ-VOCAB-001
    # ── 오디오 파일 서빙 / QA ──────────────────────────────────────────────────
    (audio.router, True),  # 원본 회의 오디오 파일 서빙 (API Key 필수)
    (qa.router, True),
    # ── 외부 도구 연계 (API Key 필수) ────────────────────────────────────────────
    (obsidian.router, True),  # SPEC-OBSIDIAN-001: Obsidian vault export
]
