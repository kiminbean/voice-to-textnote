# Implementation Plan: SPEC-COLLAB-001

## 회의록 실시간 공동 편집

## 개요

WebSocket 기반 실시간 공동 편집 시스템. Per-field LWW 충돌 해결, Redis Pub/Sub 브로드캐스트, Presence 관리, Flutter 클라이언트 구현.

## 요구사항 모듈 (5개)

### REQ-COLLAB-001-001: WebSocket 통신 [P0-CRITICAL]

**EARS**: 인증된 사용자가 회의록에 접속했을 때, 시스템은 WebSocket 연결을 설정해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 001-01 | WS /api/v1/collab/{task_id}/ws 엔드포인트 | P0 |
| 001-02 | JWT 쿼리 파라미터 인증 | P0 |
| 001-03 | 연결 시 문서 스냅샷 전송 | P0 |
| 001-04 | 연결 해제 시 Presence 제거 | P0 |

### REQ-COLLAB-001-002: LWW 충돌 해결 [P0-CRITICAL]

**EARS**: 동시 편집 시 서버 타임스탬프가 최신인 변경을 우선 적용해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 002-01 | 서버 타임스탬프 부여 | P0 |
| 002-02 | 필드별 최종 수정 시각 추적 | P0 |
| 002-03 | LWW 적용 (later wins) | P0 |
| 002-04 | 셀 단위 독립 편집 | P0 |

### REQ-COLLAB-001-003: Room + Presence [P0]

**EARS**: 사용자 입장 시 Room 생성 및 활성 사용자 브로드캐스트.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 003-01 | task_id별 Room (max 5) | P0 |
| 003-02 | 입장/퇴장 Presence 브로드캐스트 | P0 |
| 003-03 | 활성 사용자 아바타 | P1 |
| 003-05 | 6번째 사용자 거부 (4403) | P1 |

### REQ-COLLAB-001-004: Debounced 영속화 [P1]

**EARS**: Redis 즉시 저장, 3초 후 또는 퇴장 시 DB 저장.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 004-01 | Redis collab:doc:{task_id} 즉시 갱신 | P0 |
| 004-02 | 3초 debounce DB 저장 | P1 |
| 004-03 | 마지막 사용자 퇴장 시 flush | P1 |

### REQ-COLLAB-001-005: Flutter 클라이언트 [P0]

**EARS**: WebSocket 연결 후 실시간 변경사항 화면 반영.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 005-01 | CollabService (web_socket_channel) | P0 |
| 005-02 | CollabProvider (AsyncNotifier) | P0 |
| 005-03 | 자동 재연결 (backoff) | P1 |
| 005-04 | Presence 아바타 위젯 | P1 |

## 기술 스택

**Backend**: FastAPI WebSocket, Redis Pub/Sub, SQLAlchemy 2.0
**Client**: web_socket_channel, Riverpod AsyncNotifier

## 작업 분해 (Task Decomposition)

### Phase 1: Backend WebSocket Core (P0)

- T-001: `collab_models.py` — CollabSession 모델 생성
- T-002: `schemas/collab.py` — WS 메시지 Pydantic 스키마
- T-003: `collab_service.py` — LWW 충돌 해결 + Redis 영속화
- T-004: `collab.py` — WebSocket 엔드포인트 + WS auth helper
- T-005: `registry.py` — 라우터 등록

### Phase 2: Backend Tests (P0)

- T-006: LWW 충돌 해결 단위 테스트
- T-007: WebSocket 연결/인증 단위 테스트
- T-008: Presence 관리 단위 테스트
- T-009: Debounced 영속화 단위 테스트

### Phase 3: Flutter Client (P0-P1)

- T-010: `collab_service.dart` — WebSocket 클라이언트
- T-011: `collab_provider.dart` — AsyncNotifier 상태 관리
- T-012: `presence_overlay.dart` — 활성 사용자 위젯
- T-013: 자동 재연결 로직 (exponential backoff)

### Phase 4: 통합 및 마무리 (P1)

- T-014: 회의록 화면에 collab 통합
- T-015: Presence 아바타 UI
- T-016: 테스트 실행 및 회귀 검증

## 위험 분석

| 위험 | 확률 | 영향 | 완화 |
|------|------|------|------|
| WebSocket auth가 미들웨어와 충돌 | 중간 | 높음 | 쿼리 파라미터 기반 별도 auth helper |
| Redis Pub/Sub 메시지 손실 | 낮음 | 중간 | 클라이언트 재연결 시 스냅샷 동기화 |
| 동시 편집 시 LWW 정확성 | 중간 | 높음 | 단위 테스트로 검증 |
| DB flush 경쟁 조건 | 낮음 | 중간 | asyncio.Lock 사용 |

## 검증 전략

1. **단위 테스트**: LWW, auth, Presence, debounce 각 로직별
2. **회귀 테스트**: 기존 백엔드 전체 + Flutter 전체 통과
3. **통합 테스트**: WebSocket 연결 → 편집 → 브로드캐스트 → 동기화

---
*작성일: 2026-06-13*
*작성자: Sisyphus*
*상태: draft*
