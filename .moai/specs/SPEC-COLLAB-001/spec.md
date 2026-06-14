---
id: SPEC-COLLAB-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-14"
updated: "2026-06-13"
author: Sisyphus
priority: high
issue_number: 23
depends_on: SPEC-TEAM-001
---

# SPEC-COLLAB-001: 회의록 실시간 공동 편집

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 초기 작성 | Sisyphus |
| 1.0.1 | 2026-06-14 | 구현 및 검증 완료 — 협업 서비스 회귀 테스트 통과 | Codex |

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| Backend | FastAPI + WebSocket + Redis Pub/Sub |
| Frontend | Flutter + web_socket_channel + Riverpod |
| DB | SQLAlchemy + SQLite(prod: PostgreSQL) |
| 인증 | JWT (기존 SPEC-TEAM-001 시스템 재사용) |
| 실시간 | Redis Pub/Sub → WebSocket broadcast |

## 2. 가정 (Assumptions)

- SPEC-TEAM-001 JWT 인증 시스템이 정상 동작한다
- Redis가 실행 중이며 Pub/Sub을 지원한다
- 동시 편집자는 최대 5명이다
- 회의록은 이미 생성되어 task_id로 식별 가능하다
- 셀 단위(field-level) 편집이 기본 단위다

## 3. 요구사항 (Requirements)

### REQ-COLLAB-001-001: WebSocket 실시간 통신 채널 [P0-CRITICAL]

**EARS 형식**: 인증된 사용자가 회의록 페이지에 접속했을 때, 시스템은 WebSocket 연결을 설정하고 실시간 편집 이벤트를 수신해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-COLLAB-001-001-01 | `WS /api/v1/collab/{task_id}/ws` 엔드포인트 제공 | P0 | [NEW] |
| REQ-COLLAB-001-001-02 | JWT 토큰을 쿼리 파라미터(`?token=`)로 인증 | P0 | [NEW] |
| REQ-COLLAB-001-001-03 | 연결 시 현재 문서 스냅샷 전송 | P0 | [NEW] |
| REQ-COLLAB-001-001-04 | 연결 해제 시 Presence에서 제거 | P0 | [NEW] |
| REQ-COLLAB-001-001-05 | 잘못된 토큰 시 close code 4401로 종료 | P1 | [NEW] |

---

### REQ-COLLAB-001-002: Per-field LWW 충돌 해결 [P0-CRITICAL]

**EARS 형식**: 두 사용자가 동일한 필드를 동시에 편집했을 때, 시스템은 서버 타임스탬프가 더 최신인 변경을 우선 적용해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-COLLAB-001-002-01 | 편집 메시지 수신 시 서버 타임스탬프 부여 | P0 | [NEW] |
| REQ-COLLAB-001-002-02 | 필드별 최종 수정 시각 추적 | P0 | [NEW] |
| REQ-COLLAB-001-002-03 | LWW: later timestamp wins | P0 | [NEW] |
| REQ-COLLAB-001-002-04 | 셀 단위 독립 편집 (field-level granularity) | P0 | [NEW] |
| REQ-COLLAB-001-002-05 | 전체 문서는 JSON 구조로 관리 | P1 | [NEW] |

---

### REQ-COLLAB-001-003: Room 관리 및 Presence [P0]

**EARS 형식**: 사용자가 회의록에 입장했을 때, 시스템은 Room을 생성하고 활성 사용자 목록을 모든 참여자에게 브로드캐스트해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-COLLAB-001-003-01 | task_id별 Room 관리 (최대 5명) | P0 | [NEW] |
| REQ-COLLAB-001-003-02 | 입장/퇴장 시 Presence 브로드캐스트 | P0 | [NEW] |
| REQ-COLLAB-001-003-03 | 활성 사용자 아바타 목록 제공 | P1 | [NEW] |
| REQ-COLLAB-001-003-04 | 편집 중인 필드 표시 (cursor presence) | P2 | [NEW] |
| REQ-COLLAB-001-003-05 | 6번째 사용자 입장 시 거부 (close 4403) | P1 | [NEW] |

---

### REQ-COLLAB-001-004: Debounced 영속화 [P1]

**EARS 형식**: 사용자가 편집을 수행했을 때, 시스템은 Redis에 즉시 저장하고 3초 후 또는 퇴장 시 DB에 저장해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-COLLAB-001-004-01 | Redis `collab:doc:{task_id}` 즉시 갱신 | P0 | [NEW] |
| REQ-COLLAB-001-004-02 | 3초 debounce 후 DB 저장 | P1 | [NEW] |
| REQ-COLLAB-001-004-03 | Room의 마지막 사용자 퇴장 시 즉시 DB flush | P1 | [NEW] |

---

### REQ-COLLAB-001-005: Flutter 클라이언트 [P0]

**EARS 형식**: 사용자가 회의록을 조회할 때, 시스템은 WebSocket에 연결하고 실시간 변경사항을 화면에 반영해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-COLLAB-001-005-01 | web_socket_channel 기반 CollabService | P0 | [NEW] |
| REQ-COLLAB-001-005-02 | Riverpod AsyncNotifier CollabProvider | P0 | [NEW] |
| REQ-COLLAB-001-005-03 | 자동 재연결 (exponential backoff) | P1 | [NEW] |
| REQ-COLLAB-001-005-04 | Presence 아바타 위젯 | P1 | [NEW] |
| REQ-COLLAB-001-005-05 | 편집 중 필드 하이라이트 | P2 | [NEW] |

---

## 4. MVP 범위에서 제외

| 기능 | 제외 사유 | 향후 SPEC |
|------|---------|-----------|
| Operational Transform (OT) | LWW로 충분함 | — |
| 음성 채팅 | 범위 과대 | SPEC-COLLAB-002 |
| 버전 타임라인 UI | 기존 versions API로 충분 | — |
| 오프라인 편집 큐 | 복잡도 과대 | — |

## 5. 기술 설계

```
┌─────────────────────────────────────────────┐
│  Flutter Client                              │
│  ┌─────────────────────────────────────────┐ │
│  │ CollabProvider (AsyncNotifier)          │ │
│  │  → CollabService (web_socket_channel)   │ │
│  │  → PresenceOverlay widget               │ │
│  └─────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────┘
               │ WebSocket (?token=JWT)
┌──────────────▼──────────────────────────────┐
│  FastAPI WebSocket Endpoint                  │
│  WS /api/v1/collab/{task_id}/ws             │
│  ┌─────────────────────────────────────────┐ │
│  │ WS Auth Helper (query param JWT decode) │ │
│  │ ConnectionManager (Room별 연결 관리)     │ │
│  │ CollabService (LWW + Redis + DB)        │ │
│  └─────────────────────────────────────────┘ │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────┼──────────┐
    │          │          │
┌───▼──┐  ┌───▼───┐  ┌──▼──────┐
│ Redis│  │  DB   │  │Pub/Sub  │
│(LWW  │  │(flush)│  │broadcast│
│state)│  │       │  │         │
└──────┘  └───────┘  └─────────┘
```

### 신규 파일

```
backend/
├── app/api/v1/collaboration/
│   └── collab.py                      [NEW] WS endpoint
├── app/dependencies.py                [MODIFY] collab_service factory
├── schemas/
│   └── collab.py                      [NEW] WS message schemas
├── services/
│   └── collab_service.py              [NEW] LWW + Redis + DB
├── db/
│   └── collab_models.py               [NEW] CollabSession model
├── app/api/v1/registry.py             [MODIFY] register collab router

client/
├── lib/services/collab_service.dart   [NEW] WebSocket client
├── lib/providers/collab_provider.dart [NEW] AsyncNotifier
├── lib/widgets/presence_overlay.dart  [NEW] Active users widget
```

## 6. 의존성 (Dependencies)

| 선행 SPEC | 내용 |
|-----------|------|
| SPEC-TEAM-001 | JWT 인증, User 모델 |

**Backend 의존성**:
```python
# 기존 의존성으로 충분 (FastAPI WebSocket 내장, Redis 기존 클라이언트)
```

**Client 의존성**:
```yaml
web_socket_channel: ^3.0.0  # 이미 pubspec.yaml에 존재
```

## 7. 구현 현황

| 항목 | 상태 |
|------|------|
| WebSocket 엔드포인트 | 미구현 |
| LWW 충돌 해결 | 미구현 |
| Presence 관리 | 미구현 |
| Flutter 클라이언트 | 미구현 |
| 기존 WebSocket 코드 | 없음 (최초 구현) |

## 8. 기술 제약사항

| 제약 | 설명 |
|------|------|
| 최대 동시 편집자 | 5명 (Room 제한) |
| WebSocket 인증 | 헤더 불가 → 쿼리 파라미터 사용 |
| DB flush 주기 | 3초 debounce (과도한 쓰기 방지) |
| Redis TTL | Room 비어있으면 1시간 후 만료 |

---
*SPEC ID: SPEC-COLLAB-001*
*생성일: 2026-06-13*
*상태: completed*
