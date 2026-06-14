---
id: SPEC-REFACTOR-001
version: 1.0.0
status: completed
created: 2026-06-03
author: MoAI
---

# 구현 계획: SPEC-REFACTOR-001 Backend Structure Refactoring

## 접근 전략

### 원칙
1. **증분적(Incremental)**: 각 Phase는 독립적으로 배포 가능
2. **후진 호환성**: 기존 API 계약(URL, 상태코드, 응답형식) 유지
3. **테스트 우선**: 변경 전후로 테스트 통과 확인
4. **파일 단위 마이그레이션**: 한 번에 하나의 라우터/서비스만 수정

### 전제 조건
- Phase 간 순차 의존성: 1 → 2 → 3 → 4
- Phase 1, 2는 병렬 진행 가능 (서로 독립적)
- Phase 3은 Phase 2 완료 후 시작
- Phase 4은 모든 Phase 완료 후 진행 (선택적)

---

## Phase 1: 공통 에러/응답 패턴 (Priority High)

### Primary Goal: 에러 처리 일관화

#### Step 1-1: 예외 계층 확장
- **대상 파일**: `backend/app/exceptions.py`
- **작업 내용**:
  - `NotFoundError(UnprocessableEntity)` 추가 (404)
  - `UnauthorizedError(VoiceNoteError)` 추가 (401)
  - `ForbiddenError(VoiceNoteError)` 추가 (403)
  - `ConflictError(VoiceNoteError)` 추가 (409)
  - `RateLimitError(VoiceNoteError)` 추가 (429)
- **검증**: 기존 예외 테스트 통과 + 신규 예외 테스트 추가

#### Step 1-2: 에러 헬퍼 함수 생성
- **신규 파일**: `backend/app/errors.py`
- **작업 내용**:
  ```python
  def not_found(msg="리소스를 찾을 수 없습니다") -> NoReturn:
      raise NotFoundError(message=msg)
  
  def unauthorized(msg="인증이 필요합니다") -> NoReturn:
      raise UnauthorizedError(message=msg)
  
  def forbidden(msg="접근 권한이 없습니다") -> NoReturn:
      raise ForbiddenError(message=msg)
  
  def bad_request(msg: str) -> NoReturn:
      raise ValidationError(message=msg)
  
  def conflict(msg: str) -> NoReturn:
      raise ConflictError(message=msg)
  ```
- **검증**: 헬퍼 함수 단위 테스트

#### Step 1-3: 라우터 마이그레이션 (파일 단위)
- **대상**: 30+ 라우터 파일
- **작업 순서** (영향도 낮은 것부터):
  1. `sentiment.py` - 단순 CRUD 패턴
  2. `bookmarks.py` - JWT 인증 패턴
  3. `keywords.py` - 서비스 계층 패턴
  4. `tags.py` - 서비스 계층 패턴
  5. `qa.py` - 서비스 계층 패턴
  6. `versions.py` - 서비스 계층 패턴
  7. `vocabulary.py` - 서비스 계층 패턴
  8. `speakers.py` - 복합 서비스 패턴
  9. `webhooks.py` - 서비스 계층 패턴
  10. `search.py` - 서비스 + Redis 패턴
  11. `history.py` - DB + Redis 패턴
  12. `statistics.py`, `dashboard.py`, `enhanced_statistics.py`
  13. `export.py` - 복잡한 에러 처리
  14. `minutes.py`, `summary.py` - 파이프라인 연동
  15. `transcription.py`, `batch.py` - 핵심 비즈니스
  16. `auth.py` - 인증 로직
  17. `meetings.py`, `teams.py` - 권한 체크
- **각 파일 작업**:
  - `from fastapi import HTTPException` 제거
  - `from backend.app.errors import not_found, unauthorized, ...` 추가
  - `raise HTTPException(status_code=404, detail=...)` → `raise not_found(...)`
- **검증**: 각 파일 마이그레이션 후 테스트 실행

#### Step 1-4: 응답 형식 통일
- **대상**: 11개 bare dict 반환 엔드포인트
- **작업 내용**:
  - 비동기 작업 생성 응답용 `TaskCreatedResponse` 스키마 생성
  - `minutes.py`, `summary.py`, `sentiment.py`, `diarization.py` 등의 dict 반환을 스키마로 교체
- **검증**: 응답 JSON 구조 동일 확인

---

## Phase 2: 서비스 계층 분리 (Priority High, Phase 1과 병렬 가능)

### Primary Goal: 모델/서비스 물리적 분리

#### Step 2-1: 서비스 파일 이동
- **이동 대상** (`backend/db/` → `backend/services/`):
  | 소스 | 대상 |
  |------|------|
  | `db/auth_service.py` | `services/auth_service.py` |
  | `db/bookmark_service.py` | `services/bookmark_service.py` |
  | `db/meeting_share_service.py` | `services/meeting_share_service.py` |
  | `db/search_service.py` | `services/search_service.py` |
  | `db/speaker_service.py` | `services/speaker_service.py` |
  | `db/speaker_voice_service.py` | `services/speaker_voice_service.py` |
  | `db/sync_service.py` | `services/sync_service.py` |
  | `db/tag_service.py` | `services/tag_service.py` |
  | `db/team_service.py` | `services/team_service.py` |
  | `db/version_service.py` | `services/version_service.py` |
  | `db/vocabulary_service.py` | `services/vocabulary_service.py` |
  | `db/webhook_service.py` | `services/webhook_service.py` |

#### Step 2-2: Import 경로 업데이트
- **대상**: 모든 파일에서 `from backend.db.xxx_service import` → `from backend.services.xxx_service import`
- **자동화**: sed/grep으로 일괄 변경 후 개별 확인
- **검증**: 전체 테스트 실행

#### Step 2-3: `backend/db/__init__.py` 정리
- 서비스 export 제거, 모델 export만 유지
- `backend/services/__init__.py`에 서비스 export 추가 (선택적)

---

## Phase 3: 서비스 의존성 주입 (Priority Medium, Phase 2 완료 후)

### Secondary Goal: DI 패턴 일관화

#### Step 3-1: 서비스 의존성 프로바이더 생성
- **신규 파일**: `backend/app/service_deps.py`
- **작업 내용**: 각 서비스에 대한 FastAPI Depends() 프로바이더 정의
  ```python
  def get_bookmark_service() -> BookmarkService:
      return BookmarkService()
  
  def get_search_service() -> SearchService:
      return SearchService()
  # ... 각 서비스별 프로바이더
  ```

#### Step 3-2: 라우터 마이그레이션
- **대상**: 15+ 라우터의 `_service = XxxService()` 패턴
- **작업 내용**:
  - 모듈 레벨 인스턴스 제거
  - `Depends(get_xxx_service)`로 교체
- **검증**: 각 라우터 마이그레이션 후 테스트

#### Step 3-3: DB 엔진 생명주기 개선
- **대상**: `backend/app/dependencies.py`
- **작업 내용**:
  - `_db_engine` 생성을 lifespan으로 이동
  - `dependencies.py`는 app.state에서 엔진 참조
- **검증**: 앱 시작/종료 시나리오 테스트

---

## Phase 4: 라우터 구조 개선 (Priority Low, 선택적)

### Final Goal: 라우터 도메인 그룹핑

#### Step 4-1: 도메인 디렉토리 생성
- **신규 디렉토리 구조**:
  ```
  backend/app/api/v1/
  ├── transcription/     # batch, transcription, diarization
  ├── minutes/           # minutes, summary, sentiment, tags, keywords, action_items
  ├── collaboration/     # teams, meetings, bookmarks, webhooks, versions
  ├── analytics/         # statistics, dashboard, enhanced_statistics, advanced_search
  ├── audio/             # audio, audio_analysis, audio_preprocess, quality_assessment
  ├── admin/             # admin, health, history, export
  ├── auth/              # auth, devices
  └── registry.py
  ```

#### Step 4-2: 라우터 이동
- 각 파일을 해당 도메인 디렉토리로 이동
- 각 디렉토리에 `__init__.py` 생성 (라우터 export)
- URL prefix는 `/api/v1/...` 그대로 유지

#### Step 4-3: 레지스트리 패턴 도입
- **신규 파일**: `backend/app/api/v1/registry.py`
- **작업 내용**:
  ```python
  from backend.app.api.v1.transcription import batch, transcription, diarization
  from backend.app.api.v1.minutes import minutes, summary, sentiment
  # ...
  
  ROUTER_GROUPS = { ... }
  
  def register_all_routers(app: FastAPI) -> None:
      """모든 라우터를 등록하는 헬퍼"""
      ...
  ```
- `main.py`의 80줄 라우터 등록을 `register_all_routers(app)` 호출로 대체

#### Step 4-4: main.py 간소화
- 라우터 등록을 registry에 위임
- main.py는 앱 설정, 미들웨어, lifespan에 집중

---

## 리스크 및 대응

| 리스크 | 확률 | 영향 | 대응 전략 |
|--------|------|------|-----------|
| Import 경로 변경으로 테스트 대량 실패 | 중간 | 중간 | 파일 단위 이동 + 즉시 테스트 |
| 서비스 이동 시 순환 참조 발생 | 낮음 | 높음 | 의존성 그래프 사전 분석 |
| 에러 처리 변경으로 응답 형식 변화 | 낮음 | 높음 | error_handlers.py가 최종 응답 보장 |
| Phase 간 충돌 (병렬 작업 시) | 중간 | 중간 | Phase 1, 2는 다른 파일 수정 |

---

## 마일스톤

| Milestone | Phase | 완료 기준 |
|-----------|-------|-----------|
| M1: 에러 헬퍼 | 1 | errors.py 생성 + 예외 계층 확장 + 테스트 통과 |
| M2: 라우터 에러 마이그레이션 | 1 | 30+ 라우터 HTTPException 제거 + 전체 테스트 통과 |
| M3: 응답 형식 통일 | 1 | bare dict 반환 0건 |
| M4: 서비스 이동 | 2 | 12개 서비스 파일 이동 + import 업데이트 + 테스트 통과 |
| M5: DI 전환 | 3 | 모듈레벨 인스턴스 0건 + Depends() 사용 |
| M6: 라우터 그룹핑 | 4 | 도메인별 디렉토리 구성 + registry.py 도입 |
