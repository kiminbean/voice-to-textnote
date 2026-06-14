---
id: SPEC-REFACTOR-001
version: 1.0.0
status: completed
created: 2026-06-03
author: MoAI
---

# 코드베이스 분석: SPEC-REFACTOR-001

## 분석 개요

- **분석 일자**: 2026-06-03
- **분석 대상**: `backend/` 디렉토리 전체
- **분석 방법**: 파일 구조 스캔, 패턴 검색(grep), 대표 파일 독해

---

## 1. 에러 처리 패턴 분석

### 현재 상태

| 지표 | 수치 | 비고 |
|------|------|------|
| `raise HTTPException` in routers | **158건** | VoiceNoteError 우회 |
| VoiceNoteError 서브클래스 | **3개** | AudioProcessingError, StorageError, PipelineError |
| 전역 에러 핸들러 | **3개** | VoiceNoteError, ValidationError, Exception |
| inline try/except in routers | **53건** | 비즈니스 로직 누수 |
| status_code별 HTTPException | | 404: 15건, 422: 11건, 403: 9건, 400: 5건, 401: 3건, 409: 1건 |

### Anti-pattern 예시

**예시 1: 직접 HTTPException 사용** (`sentiment.py:90`)
```python
# Current - VoiceNoteError 계층을 우회
raise HTTPException(status_code=404, detail="감정 분석 작업을 찾을 수 없습니다.")

# Proposed - VoiceNoteError 계층 활용
from backend.app.errors import not_found
raise not_found("감정 분석 작업을 찾을 수 없습니다.")
```

**예시 2: 응답 형식 불일치** (`sentiment.py:66`)
```python
# Current - bare dict 반환 (response_model 없음)
return {
    "task_id": task_id,
    "minutes_task_id": request.minutes_task_id,
    "status": TaskStatus.pending.value,
    "status_url": f"/api/v1/sentiment/{task_id}/status",
    "result_url": f"/api/v1/sentiment/{task_id}",
    "created_at": now.isoformat(),
}

# Proposed - Pydantic 스키마 반환
return TaskCreatedResponse(
    task_id=task_id,
    status=TaskStatus.pending.value,
    status_url=f"/api/v1/sentiment/{task_id}/status",
    result_url=f"/api/v1/sentiment/{task_id}",
    created_at=now,
)
```

**예시 3: 인라인 try/except** (`transcription.py` - 7개 try/except)
```python
# Current - 라우터에 비즈니스 로직이 포함
try:
    vocab_service = VocabularyService()
    vocabs = await vocab_service.get_active_vocabs(db, user_id=user.id)
except Exception:
    vocabs = []
```

### 긍정적 패턴 (유지)

**error_handlers.py** - 잘 설계된 전역 예외 핸들러:
```python
# 모든 예외를 일관된 JSON 형식으로 변환
{
    "error_code": "...",
    "message": "...",
    "request_id": "..."  # structlog에서 추출
}
```

**exceptions.py** - 깔끔한 예외 계층:
```python
VoiceNoteError (base)
├── AudioProcessingError (422)
├── StorageError (500)
└── PipelineError (500)
```

---

## 2. 서비스 계층 분석

### 현재 서비스 위치 분포

| 위치 | 파일 수 | 파일 목록 |
|------|---------|-----------|
| `backend/db/` | **13개** | auth_service, bookmark_service, meeting_share_service, quality_feedback (모델만), search_service, speaker_service, speaker_voice_service, sync_service, tag_service, team_service, version_service, vocabulary_service, webhook_service |
| `backend/services/` | **7개** | advanced_search, enhanced_statistics, keyword_service, oauth_service, push_service, qa_service, quality_service, statistics, webhook_notifier |

### Anti-pattern: 모델/서비스 혼재

`backend/db/` 디렉토리에는 모델과 서비스가 혼재:
```
backend/db/
├── auth_models.py         # 모델
├── auth_service.py        # 서비스 (혼재)
├── bookmark_models.py     # 모델
├── bookmark_service.py    # 서비스 (혼재)
├── engine.py              # DB 엔진
├── models.py              # 공통 모델 (TaskResult)
├── search_models.py       # 모델
├── search_service.py      # 서비스 (혼재)
├── speaker_models.py      # 모델
├── speaker_service.py     # 서비스 (혼재)
├── ...
```

**문제점**:
- `backend/db/`의 의미가 불명확 (모델? 서비스? 둘 다?)
- 신규 개발자가 서비스 위치를 찾기 어려움
- import 경로가 일관되지 않음

### 모듈레벨 서비스 인스턴스 (21건)

```python
# bookmarks.py:29
_service = BookmarkService()

# tags.py:37
_service = TagService()

# keywords.py:24
_service = KeywordService()

# speakers.py:37-38
_service = SpeakerService()
_voice_service = SpeakerVoiceService()

# auth.py:53
_auth_service = AuthService()
```

**문제점**:
- 테스트 시 mock 주입이 어려움
- 서비스 수명 주기 관리 불가
- FastAPI Depends() 패턴과 불일치

---

## 3. 의존성 구조 분석

### 의존성 사용 통계

| 패턴 | 사용 횟수 | 비고 |
|------|-----------|------|
| `Depends(get_db_session)` | **83건** (API) / **190건** (전체) | DB 세션 주입 |
| `Depends(get_current_user)` | **51건** | JWT 인증 |
| `Depends(get_redis_client)` | **51건** | Redis 직접 접근 |
| `Depends(verify_api_key)` | 라우터 레벨 | API Key 인증 |

### 인증 전략 이중 구조

라우터마다 서로 다른 인증 방식 적용:

```python
# main.py - 라우터 레벨 API Key 인증
app.include_router(transcription.router, prefix=api_prefix, dependencies=_auth)

# bookmarks.py - 엔드포인트 레벨 JWT 인증
async def create_bookmark(
    user: User = Depends(get_current_user),  # JWT
):
```

**문제점**: 두 인증 전략(API Key vs JWT)이 명확히 문서화되지 않음.

### DB 엔진 모듈레벨 생성

```python
# dependencies.py (top-level)
_db_engine = create_engine(database_url=settings.database_url or None)
_session_factory = get_session_factory(_db_engine)
```

**문제점**: import 시점에 DB 연결이 생성됨 → 테스트 격리 어려움

---

## 4. API 라우터 구조 분석

### 라우터 파일 현황 (30+ 파일, flat 구조)

```
backend/app/api/v1/
├── __init__.py
├── action_items.py      # 액션 아이템
├── admin.py             # 관리
├── advanced_search.py   # 고급 검색
├── audio.py             # 오디오
├── audio_analysis.py    # 오디오 분석
├── audio_preprocess.py  # 오디오 전처리
├── auth.py              # 인증
├── batch.py             # 배치
├── bookmarks.py         # 북마크
├── calendar.py          # 캘린더
├── dashboard.py         # 대시보드
├── devices.py           # 디바이스
├── diarization.py       # 화자 분리
├── enhanced_statistics.py # 고급 통계
├── export.py            # 내보내기
├── health.py            # 헬스체크
├── history.py           # 이력
├── keywords.py          # 키워드
├── meetings.py          # 회의 공유
├── minutes.py           # 회의록
├── qa.py                # Q&A
├── quality_assessment.py # 품질 평가
├── search.py            # 검색
├── sentiment.py         # 감정 분석
├── speakers.py          # 화자 프로필
├── statistics.py        # 통계
├── stream.py            # SSE 스트림
├── summary.py           # 요약
├── tags.py              # 태그
├── teams.py             # 팀
├── templates.py         # 템플릿
├── transcription.py     # STT 전사
├── versions.py          # 버전 관리
├── vocabulary.py        # 어휘
└── webhooks.py          # 웹훅
```

### main.py 라우터 등록 (80+ 줄)

```python
# 현재 패턴 - 각 라우터를 개별적으로 등록
app.include_router(batch.router, prefix=api_prefix, dependencies=_auth)
app.include_router(transcription.router, prefix=api_prefix, dependencies=_auth)
app.include_router(diarization.router, prefix=api_prefix, dependencies=_auth)
# ... 30+줄 반복
```

### 도메인 분류 제안

| 도메인 그룹 | 라우터 | 인증 전략 |
|-------------|--------|-----------|
| **transcription/** | batch, transcription, diarization, stream | API Key |
| **minutes/** | minutes, summary, sentiment, tags, keywords, action_items | API Key |
| **collaboration/** | teams, meetings, bookmarks, webhooks, versions | JWT |
| **analytics/** | statistics, dashboard, enhanced_statistics, advanced_search, search | Mixed |
| **audio/** | audio, audio_analysis, audio_preprocess, quality_assessment | Mixed |
| **admin/** | admin, health, history, export | API Key |
| **auth/** | auth, devices | Public/JWT |

---

## 5. 응답 형식 분석

### response_model 사용 vs 미사용

| 유형 | 수량 | 비율 |
|------|------|------|
| `response_model=` 지정 | **99** | 90% |
| bare dict 반환 | **11** | 10% |
| `JSONResponse` 직접 사용 | **4** | <5% |

### bare dict 반환 엔드포인트 (11건)

| 파일 | 엔드포인트 | 반환 내용 |
|------|------------|-----------|
| `sentiment.py:66` | POST /sentiment | 작업 생성 확인 |
| `minutes.py:94` | POST /minutes | 작업 생성 확인 |
| `summary.py:95` | POST /summary | 작업 생성 확인 |
| `summary.py:161` | POST /summary/{id}/retry | 재시도 확인 |
| `diarization.py:92` | POST /diarization | 작업 생성 확인 |
| `tags.py:157` | DELETE /tags/{task_id} | 삭제 결과 |
| `quality_assessment.py:270` | POST /quality/assess | 작업 생성 확인 |
| `admin.py:51` | POST /admin/retention/run | 실행 결과 |
| `calendar.py:246` | POST /calendar/events | 이벤트 생성 |
| `advanced_search.py:180` | POST /search/advanced | 검색 결과 |
| `advanced_search.py:209` | POST /search/analyze | 분석 결과 |

---

## 6. 요약 및 우선순위

### 발견된 Anti-patterns (심각도 순)

1. **HTTPException 158건** (높음): VoiceNoteError 계층이 무의미해짐
2. **비즈니스 로직 누수 53건** (높음): 라우터에 try/except 과다
3. **서비스 위치 혼재** (중간): db/와 services/에 분산
4. **모듈레벨 인스턴스 21건** (중간): 테스트 가능성 저하
5. **응답 형식 불일치 11건** (낮음): bare dict 반환
6. **라우터 flat 구조** (낮음): 30+ 파일이 그룹핑 없이 존재

### 기대 효과

| 개선 영역 | Before | After | 효과 |
|-----------|--------|-------|------|
| 에러 처리 일관성 | 158건 HTTPException | 0건 (VoiceNoteError만) | 에러 추적/핸들링 일원화 |
| 서비스 위치 | 2곳 혼재 | 1곳 (services/) | 탐색성 향상 |
| DI 패턴 | 21건 모듈레벨 | 0건 (Depends만) | 테스트 용이성 |
| 응답 일관성 | 11건 bare dict | 0건 (response_model만) | API 계약 명확화 |
| main.py 라인 수 | 280줄 | ~150줄 | 유지보수성 향상 |
