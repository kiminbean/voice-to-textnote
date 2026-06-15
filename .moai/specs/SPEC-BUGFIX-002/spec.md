---
id: SPEC-BUGFIX-002
version: "1.0.0"
status: planned
created: "2026-06-15"
updated: "2026-06-15"
author: MoAI
priority: high
issue_number: 0
---

# SPEC-BUGFIX-002: 버그 fix 후속 작업 — 테스트 강화, 근본 해결, 회귀 방지

## HISTORY

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2026-06-15 | 1.0.0 | Initial SPEC — 후속 작업 6개 영역 정의 | MoAI |

## 개요

SPEC-BUGFIX-001 및 loop 워크플로우에서 fix한 18건 버그에 대한 후속 작업을 수행한다. fix 자체는 완료되었으나, 다음 영역에서 근본 해결, 회귀 방지, 운영 가시성 강화가 필요하다:

1. `asyncio.to_thread` wrap에 대한 동시성 회귀 테스트 부재 (7곳)
2. `collab_service` race condition 근본 해결 미완료 (완화만 적용)
3. `push_service` FCM 활성화 시 timebomb 예방
4. temp file/dir leak 정적 분석 CI gate 부재
5. `version_service` UniqueConstraint 마이그레이션 누락
6. `except Exception: pass → logger.warning` 변경 후 모니터링 검증

## 요구사항 (EARS Format)

### REQ-BF2-001: asyncio.to_thread 회귀 테스트

- **When** `transcription.py`, `batch.py`, `audio_analysis.py`, `export.py`, `templates.py`의 CPU-bound/blocking 함수가 `asyncio.to_thread` 없이 직접 호출될 때
- **Then** CI에서 회귀 테스트가 실패해야 한다
- **Rationale**: 7곳의 `asyncio.to_thread` wrap이 실수로 제거되는 것을 방지

**검증 방법**:
- 각 엔드포인트에 `asyncio.get_event_loop().run_in_executor` 호출 여부를 확인하는 정적 테스트
- 또는 동시 요청 시 event loop blocking 감지하는 동적 테스트 (httpx AsyncClient + concurrent requests)

### REQ-BF2-002: collab_service race condition 근본 해결

- **When** Redis Lua script를 지원하는 프로덕션 환경에서 `add_presence` 또는 `apply_edit`이 동시에 호출될 때
- **Then** 원자적 check-and-set으로 MAX_PARTICIPANTS 초과 및 LWW 위반이 발생하지 않아야 한다
- **Rationale**: 현재는 check-then-act 사이 await 없음으로 완화했으나, 단일 이벤트 루프 외 환경(Multi-worker, 분산)에서는 race 가능

**검증 방법**:
- `redis.eval()` 기반 Lua script로 `add_presence`를 원자화
- 테스트 환경에서 AsyncMock 대신 `fakeredis` (Lua 지원) 사용
- 동시 10개 `add_presence` 호출로 MAX_PARTICIPANTS=5 위반 없음 확인

### REQ-BF2-003: push_service FCM 활성화 전 to_thread wrap

- **When** `push_service.py`에서 `firebase_admin.messaging.send()`의 주석을 해제하여 FCM을 활성화할 때
- **Then** 해당 호출이 `asyncio.to_thread`로 감싸져 있어야 한다
- **Rationale**: 현재 MOCK 모드이므로 blocking 없음. 하지만 활성화 즉시 sync HTTP 호출이 async event loop를 블로킹

**검증 방법**:
- `messaging.send()` 호출 라인에 `await asyncio.to_thread(messaging.send, message)` 적용
- `# FCM-TIMEBOMB` 마커 제거
- 테스트에서 Mock messaging.send 호출 시 to_thread 경유 확인

### REQ-BF2-004: temp file/dir leak 정적 분석 gate

- **When** PR에서 `tempfile.mkdtemp`, `tempfile.mkstemp`, `NamedTemporaryFile(delete=False)`를 사용하는 코드가 추가될 때
- **Then** 대응하는 `shutil.rmtree` 또는 `unlink` cleanup 경로가 같은 PR에 포함되어야 한다
- **Rationale**: 3건의 temp dir leak이 패턴 반복으로 발생. 자동화된 gate로 재발 방지

**검증 방법**:
- AST-grep 규칙: `tempfile.mkdtemp` 호출 시 같은 함수 내에 `shutil.rmtree` 존재 여부 확인
- CI workflow: `pre-commit` hook 또는 `ruff` custom rule로 통합
- 기존 7곳의 mkdtemp 사용 패턴 분석 후 규칙 작성

### REQ-BF2-005: version_service Alembic migration

- **When** 기존 데이터베이스에 `minutes_versions` 테이블이 이미 존재할 때
- **Then** `UniqueConstraint("task_id", "version_number")`가 마이그레이션으로 추가되어야 한다
- **Rationale**: 모델에 UniqueConstraint를 추가했으나, 기존 DB에는 자동 반영되지 않음

**검증 방법**:
- Alembic migration script: `alembic revision --autogenerate -m "add unique constraint on minutes_versions"`
- 마이그레이션 실행 후 `alembic upgrade head` 성공
- 기존 데이터가 있는 경우에도 constraint 추가 성공 (데이터 중복 없음 전제)

### REQ-BF2-006: 운영 로그 모니터링 검증

- **When** 워커 태스크의 DB 저장 실패 시 `logger.warning("DB 결과 저장 실패 - Redis 캐시로 폴백")` 로그가 발생할 때
- **Then** 해당 로그가 운영 모니터링 대시보드에서 수집 및 알림되어야 한다
- **Rationale**: `except: pass`를 `logger.warning`으로 변경했으나, 실제로 수집/알림되는지 미검증

**검증 방법**:
- 구조화된 로그 포맷에 `category: "db_fallback"` 필드 추가
- Prometheus/Grafana에서 `db_fallback` 로그 카운트 메트릭 정의
- 알림 임계값: 5분당 3회 이상 발생 시 Slack/PagerDuty 알림

## 인수 기준 (Acceptance Criteria)

### AC-001: asyncio.to_thread 회귀 테스트
- transcription.py의 `get_audio_duration_seconds` 호출이 `asyncio.to_thread`를 사용하는지 확인하는 테스트 통과
- export.py의 PDF/DOCX 생성이 `asyncio.to_thread`를 사용하는지 확인하는 테스트 통과
- 총 7개 회귀 테스트 작성, 전부 PASS

### AC-002: collab_service Lua script
- `add_presence`가 Lua script 기반 atomic check-and-set 사용
- 동시 10개 호출 테스트에서 MAX_PARTICIPANTS=5 위반 없음
- `apply_edit`이 Lua script 기반 atomic LWW 사용
- fakeredis 기반 테스트 환경 구축

### AC-003: push_service FCM wrap
- `messaging.send()` 호출이 `asyncio.to_thread`로 감싸짐
- `# FCM-TIMEBOMB` 마커 제거
- push_service 테스트 PASS

### AC-004: temp file leak 정적 분석 gate
- AST-grep 규칙 파일 작성 (`.sgconfig.yml` 또는 별도)
- CI에서 규칙 실행, 기존 코드는 PASS (이미 fix됨)
- 의도적으로 leak 유발한 테스트 코드에서 규칙 FAIL 확인

### AC-005: version_service migration
- Alembic migration script 생성
- `alembic upgrade head` 성공
- 기존 테스트 DB에서 UniqueConstraint 적용 확인

### AC-006: 운영 로그 검증
- `db_fallback` 카테고리 필드가 로그에 포함됨
- 단위 테스트에서 로그 출력 검증
- (운영 환경 대시보드 설정은 본 SPEC 범위 외, 권장 사항으로 기록)

## 기술 접근법

### Lua Script for collab_service

```lua
-- add_presence (atomic check-and-set)
local count = redis.call('hlen', KEYS[1])
local exists = redis.call('hexists', KEYS[1], ARGV[1])
if exists == 1 then
    redis.call('hset', KEYS[1], ARGV[1], ARGV[2])
    redis.call('expire', KEYS[1], ARGV[4])
    return 1
end
if count >= tonumber(ARGV[3]) then
    return 0
end
redis.call('hset', KEYS[1], ARGV[1], ARGV[2])
redis.call('expire', KEYS[1], ARGV[4])
return 1
```

### AST-grep Rule for temp file leak

```yaml
# mkdtemp 호출 시 같은 함수 범위 내 rmtree 필요
pattern: tempfile.mkdtemp($$$ARGS)
constraint:
  has-descendant: shutil.rmtree
```

## 영향 범위

### 수정 대상 파일
- `backend/services/collab_service.py` — Lua script 통합
- `backend/services/push_service.py` — FCM to_thread wrap
- `backend/tests/unit/test_*_concurrency.py` (신규) — 회귀 테스트
- `backend/alembic/versions/xxx_add_unique_constraint.py` (신규) — migration
- `.sgconfig.yml` 또는 `.pre-commit-config.yaml` — 정적 분석 규칙

### 의존성
- `fakeredis >= 2.0` (Lua script 지원 버전) — 테스트 환경
- 기존 `ast-grep` CLI — 이미 프로젝트에 통합됨

## 우선순위

| REQ | 우선순위 | 이유 |
|-----|---------|------|
| REQ-BF2-003 | P0 | FCM 활성화 전 필수 (timebomb) |
| REQ-BF2-005 | P0 | 기존 DB 마이그레이션 누락 |
| REQ-BF2-002 | P1 | 분산 환경 전 필수 |
| REQ-BF2-001 | P1 | 회귀 방지 |
| REQ-BF2-004 | P2 | 재발 방지 자동화 |
| REQ-BF2-006 | P2 | 운영 가시성 (코드 변경 최소) |

## 제약사항

- Lua script 적용 시 fakeredis 의존성 추가 필요 (기존 AsyncMock 테스트 교체)
- AST-grep 규칙은 기존 7곳 mkdtemp 사용 패턴 분석 후 작성 (false positive 최소화)
- Alembic migration은 기존 데이터 중복 여부 사전 확인 필요
- 운영 모니터링 대시보드 설정은 본 SPEC 범위 외 (별 Ops 작업)
