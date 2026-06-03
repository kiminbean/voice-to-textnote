---
id: SPEC-REFACTOR-001
version: 1.0.0
status: draft
created: 2026-06-03
author: MoAI
---

# 인수 기준: SPEC-REFACTOR-001 Backend Structure Refactoring

## 품질 게이트 (Quality Gates)

### TRUST 5 검증

| 항목 | 기준 | 측정 방법 |
|------|------|-----------|
| Tested | 85%+ 커버리지 유지 | `pytest --cov=backend` |
| Readable | ruff lint 0 errors | `ruff check backend/` |
| Unified | black/isort 포맷팅 일치 | `black --check backend/` |
| Secured | 기존 보안 테스트 통과 | `pytest backend/tests/ -k security` |
| Trackable | Conventional commit 메시지 | `git log --oneline` 확인 |

---

## Phase 1: 공통 에러/응답 패턴 인수 기준

### AC-ERR-001: 예외 계층 확장

**Given** `backend/app/exceptions.py`에 새로운 예외 클래스가 추가됨
**When** `NotFoundError`, `UnauthorizedError`, `ForbiddenError`, `ConflictError`, `RateLimitError`를 import함
**Then** 각 예외는 `VoiceNoteError`를 상속하고 적절한 기본 `status_code`를 가져야 함

```gherkin
Scenario: NotFoundError 기본 동작
  Given NotFoundError 클래스가 정의됨
  When raise NotFoundError(message="회의를 찾을 수 없습니다") 실행
  Then error_code은 "NOT_FOUND_ERROR"이어야 함
  And status_code은 404이어야 함
  And error_handlers.py에서 JSONResponse로 변환됨
```

### AC-ERR-002: 에러 헬퍼 함수

**Given** `backend/app/errors.py`에 헬퍼 함수가 정의됨
**When** 라우터에서 `raise not_found("작업을 찾을 수 없습니다")` 호출
**Then** VoiceNoteError 서브클래스가 raise됨
**And** error_handlers.py가 이를 일관된 JSON으로 변환함

```gherkin
Scenario: not_found 헬퍼 동작
  Given errors.py에 not_found 함수가 정의됨
  When not_found("감정 분석 작업을 찾을 수 없습니다.") 호출
  Then NotFoundError가 raise됨
  And message은 "감정 분석 작업을 찾을 수 없습니다."임
  And status_code은 404임

Scenario: unauthorized 헬퍼 동작
  Given errors.py에 unauthorized 함수가 정의됨
  When unauthorized() 호출 (인자 없음)
  Then UnauthorizedError가 raise됨
  And message은 기본값 "인증이 필요합니다"임
```

### AC-ERR-003: HTTPException 제거 완료

**Given** 모든 라우터 파일이 마이그레이션 완료됨
**When** `grep -rn "HTTPException" backend/app/api/v1/` 실행
**Then** 결과가 0건이어야 함 (import 문 제외)

```gherkin
Scenario: 라우터에 HTTPException 없음
  Given Phase 1 마이그레이션이 완료됨
  When backend/app/api/v1/ 디렉토리를 스캔함
  Then "raise HTTPException" 패턴이 0건이어야 함
  And 모든 에러가 VoiceNoteError 계층을 사용해야 함
```

### AC-ERR-004: 응답 형식 일관성

**Given** 모든 엔드포인트가 response_model을 사용함
**When** `grep -rn 'return {' backend/app/api/v1/` 실행
**Then** dict 리터럴 직접 반환 없이 Pydantic 모델만 반환해야 함

```gherkin
Scenario: 비동기 작업 생성 응답
  Given POST /api/v1/sentiment 엔드포인트가 TaskCreatedResponse를 사용함
  When 감정 분석 작업을 생성함
  Then 응답이 response_model에 의해 검증됨
  And 응답 JSON에 task_id, status, created_at 필드가 포함됨
```

### AC-ERR-005: 에러 응답 형식 유지

**Given** 기존 에러 응답이 error_code, message, request_id 구조를 사용함
**When** 마이그레이션 후 동일한 에러 조건 발생
**Then** 응답 JSON 구조가 기존과 동일해야 함

```gherkin
Scenario: 404 에러 응답 형식 비교
  Given 기존 HTTPException(404, detail="작업 없음") 사용
  When NotFoundError(message="작업 없음")로 교체
  Then 응답은 {"error_code": "NOT_FOUND_ERROR", "message": "작업 없음", "request_id": "..."} 형식이어야 함
  And HTTP 상태 코드는 404로 동일함
```

---

## Phase 2: 서비스 계층 분리 인수 기준

### AC-SVC-001: 서비스 파일 이동 완료

**Given** 서비스 파일들이 `backend/db/`에서 `backend/services/`로 이동됨
**When** `ls backend/db/*_service.py` 실행
**Then** 결과가 0건이어야 함

```gherkin
Scenario: 서비스 파일 위치 확인
  Given Phase 2 마이그레이션이 완료됨
  When backend/db/ 디렉토리를 확인함
  Then *_service.py 파일이 존재하지 않아야 함
  And backend/services/에 모든 서비스 파일이 존재해야 함
```

### AC-SVC-002: Import 경로 일관성

**Given** 서비스 파일이 이동됨
**When** `grep -rn "from backend.db.*_service import" backend/` 실행
**Then** 결과가 0건이어야 함

```gherkin
Scenario: 서비스 import 경로 업데이트
  Given 모든 서비스 파일이 backend/services/로 이동됨
  When 전체 코드베이스를 스캔함
  Then "from backend.db.xxx_service import" 패턴이 0건이어야 함
  And "from backend.services.xxx_service import" 패턴이 정상 동작해야 함
```

### AC-SVC-003: 기존 기능 유지

**Given** 서비스 파일이 이동됨
**When** 전체 테스트 스위트 실행
**Then** 모든 기존 테스트가 통과해야 함

```gherkin
Scenario: 기능 회귀 없음
  Given 서비스 이동 전 테스트 N개가 통과함
  When 서비스 파일 이동 후 동일한 테스트 실행
  Then N개 테스트가 모두 통과해야 함
  And 새로운 실패가 없어야 함
```

---

## Phase 3: 서비스 의존성 주입 인수 기준

### AC-DEP-001: 모듈레벨 인스턴스 제거

**Given** 모든 라우터가 Depends() 패턴을 사용함
**When** `grep -rn "^_service = " backend/app/api/v1/` 실행
**Then** 결과가 0건이어야 함

```gherkin
Scenario: 서비스 DI 패턴
  Given Phase 3 마이그레이션이 완료됨
  When 라우터 파일을 확인함
  Then 모듈레벨 _service 인스턴스가 없어야 함
  And 모든 서비스가 Depends(get_xxx_service)로 주입되어야 함
```

### AC-DEP-002: 테스트 가능성 향상

**Given** 서비스가 Depends()로 주입됨
**When** 테스트에서 서비스를 mock해야 함
**Then** `app.dependency_overrides`로 서비스를 교체할 수 있어야 함

```gherkin
Scenario: 서비스 mock 주입
  Given BookmarkService가 Depends(get_bookmark_service)로 주입됨
  When 테스트에서 app.dependency_overrides[get_bookmark_service] = MockService 설정
  Then mock 서비스가 라우터에 주입됨
  And 실제 DB 없이 테스트 가능함
```

### AC-DEP-003: DB 엔진 생명주기

**Given** DB 엔진이 lifespan에서 생성됨
**When** 애플리케이션 시작 시
**Then** lifespan에서 엔진이 생성되고 app.state에 저장됨
**And** 종료 시 엔진이 정리됨

```gherkin
Scenario: DB 엔진 lifespan 관리
  Given DB 엔진이 모듈 import 시점이 아닌 lifespan에서 생성됨
  When FastAPI 앱이 시작됨
  Then lifespan 함수에서 DB 엔진이 생성됨
  And dependencies.py는 app.state에서 엔진을 참조함
```

---

## Phase 4: 라우터 구조 개선 인수 기준

### AC-ROUTE-001: 도메인 그룹핑

**Given** 라우터가 도메인별로 그룹핑됨
**When** `ls backend/app/api/v1/` 실행
**Then** 도메인 디렉토리가 존재해야 함 (transcription/, minutes/, collaboration/, analytics/, audio/, admin/, auth/)

```gherkin
Scenario: 도메인 디렉토리 구조
  Given Phase 4 마이그레이션이 완료됨
  When backend/app/api/v1/ 구조를 확인함
  Then transcription/ 디렉토리에 batch.py, transcription.py, diarization.py가 포함됨
  And collaboration/ 디렉토리에 teams.py, meetings.py, bookmarks.py가 포함됨
```

### AC-ROUTE-002: URL 경로 유지

**Given** 라우터 파일이 도메인 디렉토리로 이동됨
**When** 기존 API 엔드포인트 호출
**Then** 동일한 URL 경로로 접근 가능해야 함

```gherkin
Scenario: API URL 불변
  Given transcription.py가 api/v1/transcription/ 디렉토리로 이동됨
  When POST /api/v1/transcriptions 요청
  Then 정상 응답 (200/202)이 반환됨
  And URL 패턴은 변경되지 않음
```

### AC-ROUTE-003: main.py 간소화

**Given** registry.py가 도입됨
**When** `main.py`의 라우터 등록 코드 확인
**Then** `register_all_routers(app)` 호출 하나로 대체됨

```gherkin
Scenario: main.py 라우터 등록 간소화
  Given registry.py에 ROUTER_GROUPS가 정의됨
  When main.py를 확인함
  Then include_router 호출이 30줄에서 1줄(또는 소수)로 감소함
  And 모든 라우터가 정상 등록됨
```

---

## 통합 인수 기준 (전체 Phase 완료 후)

### AC-INT-001: 전체 테스트 통과

```gherkin
Scenario: 전체 테스트 스위트
  Given 모든 Phase 마이그레이션이 완료됨
  When PYTHONPATH=. venv/bin/python -m pytest backend/tests/ -v 실행
  Then 모든 테스트가 통과해야 함
  And 기존 대비 새로운 실패가 없어야 함
```

### AC-INT-002: API 계약 유지

```gherkin
Scenario: API 응답 형식 호환성
  Given 마이그레이션 전후 동일한 엔드포인트
  When 동일한 요청을 보냄
  Then 응답 상태 코드가 동일함
  And 응답 JSON 구조가 동일함
  And 응답 시간이 기존 대비 10% 이내 차이임
```

### AC-INT-003: 코드 품질 지표

```gherkin
Scenario: 정적 분석 통과
  Given 전체 마이그레이션이 완료됨
  When ruff check backend/ 실행
  Then lint 에러가 0건이어야 함
  When black --check backend/ 실행
  Then 포맷팅 에러가 0건이어야 함
```

### AC-INT-004: Anti-pattern 제거 확인

```gherkin
Scenario: Anti-pattern 제거 검증
  Given 전체 마이그레이션이 완료됨
  When 다음을 확인함:
    | 패턴 | 명령어 | 기대값 |
    |------|--------|--------|
    | HTTPException in routers | grep -rn "raise HTTPException" backend/app/api/v1/ | 0건 |
    | Module-level service | grep -rn "^_service = " backend/app/api/v1/ | 0건 |
    | Bare dict return | grep -rn "return {" backend/app/api/v1/ | 0건 |
    | Service in db dir | ls backend/db/*_service.py | 0건 |
    | Old import paths | grep -rn "from backend.db.*_service" backend/ | 0건 |
  Then 모든 anti-pattern이 제거되어야 함
```

---

## Definition of Done

- [ ] Phase 1: HTTPException 0건, bare dict 0건, 에러 헬퍼 테스트 통과
- [ ] Phase 2: 서비스 파일 이동 완료, import 경로 업데이트, 전체 테스트 통과
- [ ] Phase 3: 모듈레벨 인스턴스 0건, DI 패턴 적용, 테스트 통과
- [ ] Phase 4: 도메인 그룹핑 완료, main.py 간소화, URL 유지
- [ ] 전체: ruff lint 0건, black 포맷 일치, 85%+ 커버리지 유지
- [ ] 전체: 기존 테스트 모두 통과, API 계약 변경 없음
