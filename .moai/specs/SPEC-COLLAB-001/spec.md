# SPEC-COLLAB-001: 회의록 실시간 공동 편집 (Real-time Collaborative Meeting Minutes Editing)

| 필드 | 값 |
|------|-----|
| SPEC ID | SPEC-COLLAB-001 |
| 제목 | 회의록 실시간 공동 편집 |
| 상태 | Planned |
| 우선순위 | High |
| 생성일 | 2026-06-12 |
| 도메인 | COLLAB |
| Issue | #23 |
| 관련 SPEC | SPEC-TEAM-001 (JWT Auth/RBAC), SPEC-SSE-001 (실시간 패턴), SPEC-MIN-001 (회의록 생성) |
| Lifecycle Level | spec-anchored |

## 1. 개요

팀원들이 동일한 회의록을 실시간으로 공동 편집할 수 있는 기능. WebSocket 기반 양방향 통신과 per-field LWW(Last-Write-Wins) 충돌 해결로 2~5명 동시 편집을 지원한다.

### 1.1 배경

현재 `_MinutesTab`의 `_editedSections`는 휘발성 상태로, 화면 dispose 시 편집 내용이 손실된다. 팀 공유(SPEC-TEAM-001) 기능이 이미 존재하지만, 공유된 회의록을 여러 팀원이 동시에 편집할 수단이 없다. 본 SPEC은 편집 영속화와 실시간 동기화를 모두 해결한다.

### 1.2 설계 결정 사항

| 결정 항목 | 선택 | 이유 |
|-----------|------|------|
| 실시간 통신 | WebSocket (FastAPI 네이티브) | SSE는 단방향, 본 기능은 양방향 필요 |
| 충돌 해결 | Per-field LWW (서버 타임스탬프) | 2~5명 소규모 + 셀 단위 편집에 적합 |
| 인증 | JWT 토큰 (쿼리 파라미터 전달) | 기존 JWT 인프라 재사용, WebSocket은 HTTP 헤더 불가 |
| 권한 | 기존 TeamMember.role (RBAC) | admin/member → 편집, viewer → 읽기 전용 |
| Flutter WebSocket | web_socket_channel 패키지 | Dart 생태계 표준, 순수 Dart 구현 |
| 버전 히스토리 | **제외** (후속 SPEC 분리) | 인터뷰 결정사항, MinutesVersion 모델은 참고용 |

## 2. 환경 (Environment)

### 2.1 전제 조건

- SPEC-TEAM-001 완료: JWT 인증, RBAC (admin/member/viewer), 팀 공유 기능 동작 중
- SPEC-MIN-001 완료: 회의록 생성 및 조회 API 동작 중
- Redis 실행 중: 기존 SSE Pub/Sub와 네임스페이스 분리 필요
- Flutter 클라이언트: Riverpod 상태 관리, Dio HTTP 클라이언트 동작 중

### 2.2 제약 사항

- 동시 편집자: 최대 5명 (소규모 팀 단위)
- 편집 단위: 회의록 테이블의 개별 셀 (per-field, `_editedSections` 키 단위)
- 지연 목표: 편집 후 1초 이내 다른 사용자에게 반영
- 단일 서버 인스턴스 (M4 Mac Mini, 로컬 배포 환경)

## 3. 가정 (Assumptions)

| ID | 가정 | 신뢰도 | 위험 | 검증 방법 |
|----|------|--------|------|-----------|
| A-01 | WebSocket 연결 당 메모리 점유 < 1MB | 높음 | 낮음 | 프로파일링 |
| A-02 | 5명 동시 편집 시 LWW 충돌 빈도 < 10% | 높음 | 중간 | 부하 테스트 |
| A-03 | 서버 타임스탬프로 충돌 해결 시 사용자 체감 오차 무시 가능 | 높음 | 낮음 | 사용자 테스트 |
| A-04 | 기존 SSE Redis Pub/Sub와 WebSocket 채널 네임스페이스 분리 가능 | 높음 | 낮음 | 아키텍처 리뷰 |
| A-05 | Flutter web_socket_channel이 웹/macOS 모두 지원 | 높음 | 낮음 | 크로스 플랫폼 테스트 |

## 4. 요구사항 (Requirements)

### 4.1 Backend WebSocket Server

#### REQ-COLLAB-001 [Ubiquitous] WebSocket 연결 관리
시스템은 `WS /api/v1/collab/{task_id}/ws` 엔드포인트를 통해 WebSocket 연결을 항상 제공해야 한다(SHALL). 연결 시 JWT 토큰을 쿼리 파라미터 `?token=<jwt>`로 검증하고, 유효하지 않은 토큰은 4001 코드로 즉시 연결을 거부해야 한다(SHALL).

#### REQ-COLLAB-002 [Ubiquitous] ConnectionManager
시스템은 `task_id` 기준으로 WebSocket 연결을 room 단위로 관리해야 한다(SHALL). 각 room은 최대 5개의 동시 연결을 허용하고, 초과 시 새 연결을 4003 코드로 거부해야 한다(SHALL).

#### REQ-COLLAB-003 [Event-Driven] 연결/해제 이벤트 브로드캐스트
WHEN 사용자가 room에 입장하거나 퇴장하면 THEN 시스템은 해당 room의 모든 참여자에게 `user_joined` 또는 `user_left` 이벤트를 브로드캐스트해야 한다(SHALL). 이벤트에는 사용자 ID와 표시 이름이 포함되어야 한다(SHALL).

#### REQ-COLLAB-004 [Ubiquitous] 하트비트
시스템은 30초 간격으로 ping/pong 하트비트를 유지해야 한다(SHALL). 60초 이내 pong 응답이 없으면 연결을 종료하고 room에서 제거해야 한다(SHALL).

### 4.2 Collaborative Editing Service

#### REQ-COLLAB-010 [Event-Driven] 편집 작업 수신 및 브로드캐스트
WHEN 클라이언트가 `edit` 메시지를 전송하면 THEN 시스템은 해당 필드에 per-field LWW를 적용하고, 변경 사항을 room의 다른 모든 참여자에게 `edit_broadcast` 메시지로 브로드캐스트해야 한다(SHALL).

**edit 메시지 형식:**
```json
{
  "type": "edit",
  "field": "summary_text",
  "value": "수정된 회의 요약 내용",
  "timestamp": 0
}
```

**edit_broadcast 메시지 형식:**
```json
{
  "type": "edit_broadcast",
  "field": "summary_text",
  "value": "수정된 회의 요약 내용",
  "user_id": "uuid",
  "server_timestamp": 1718179200000
}
```

#### REQ-COLLAB-011 [State-Driven] LWW 충돌 해결
IF 서버 타임스탬프가 기존 필드 타임스탬프보다 크거나 같으면 THEN 시스템은 새 값을 수락해야 한다(SHALL). 서버가 중앙 타임스탬프를 발급하므로 클라이언트 타임스탬프는 참조용으로만 사용한다.

#### REQ-COLLAB-012 [Event-Driven] 전체 상태 동기화
WHEN 새 사용자가 room에 입장하면 THEN 시스템은 현재 회의록의 모든 필드 상태를 `sync_state` 메시지로 전송해야 한다(SHALL). 이 메시지에는 각 필드의 값, 마지막 수정자, 서버 타임스탬프가 포함되어야 한다(SHALL).

#### REQ-COLLAB-013 [Ubiquitous] 편집 단위
편집 단위는 회의록 테이블의 개별 셀(필드)이어야 한다(SHALL). 한 필드의 편집이 다른 필드에 영향을 주어서는 안 된다(SHALL NOT).

### 4.3 Persistence Layer

#### REQ-COLLAB-020 [Event-Driven] 회의록 PATCH 엔드포인트
WHEN 협업 세션에서 편집이 발생하면 THEN 시스템은 변경 사항을 Redis에 즉시 반영하고, 3초 이내에 DB에 비동기 영속화해야 한다(SHALL).

**새 엔드포인트: `PATCH /api/v1/minutes/{task_id}`**
```json
{
  "fields": {
    "summary_text": "수정된 요약",
    "action_items": "수정된 액션 아이템"
  }
}
```

#### REQ-COLLAB-021 [Ubiquitous] Redis 임시 저장
시스템은 편집 중인 회의록 상태를 Redis `collab:state:{task_id}` 키에 JSON으로 저장해야 한다(SHALL). TTL은 협업 세션 종료 후 1시간으로 설정해야 한다(SHALL).

#### REQ-COLLAB-022 [State-Driven] DB 영속화 트리거
IF 마지막 DB 저장 후 3초 이상 경과했거나 협업 세션의 마지막 참여자가 퇴장하면 THEN 시스템은 Redis 캐시의 현재 상태를 `TaskResult.result_data`에 병합하여 저장해야 한다(SHALL).

### 4.4 Flutter WebSocket Client

#### REQ-COLLAB-030 [Ubiquitous] CollabSocketService
시스템은 `web_socket_channel` 패키지를 기반으로 하는 `CollabSocketService` 클래스를 제공해야 한다(SHALL). 이 서비스는 WebSocket 연결 수립, 메시지 송수신, 자동 재연결을 담당한다.

**재연결 정책:** 연결 끊김 시 지수 백오프(1s, 2s, 4s, 최대 30s)로 자동 재연결해야 한다(SHALL).

#### REQ-COLLAB-031 [Ubiquitous] CollabMinutesNotifier
시스템은 Riverpod `AsyncNotifier<CollabMinutesState>`인 `CollabMinutesNotifier`를 제공해야 한다(SHALL). 이 노티파이어는 로컬 편집을 WebSocket으로 전송하고, 원격 편집을 수신하여 상태를 갱신한다.

**상태 구조:**
```dart
class CollabMinutesState {
  final Map<String, String> fields;         // 현재 필드 값
  final Map<String, String> editingUsers;   // field → userId (편집 중인 사용자)
  final Set<CollabUser> activeUsers;        // 현재 접속 중인 사용자 목록
  final bool isConnected;
}
```

#### REQ-COLLAB-032 [Event-Driven] 편집 전송
WHEN 사용자가 셀 편집을 완료하면 THEN `CollabMinutesNotifier`는 `edit` 메시지를 WebSocket으로 전송해야 한다(SHALL). 편집 완료는 TextField 포커스 해제(onEditingComplete) 시점으로 정의한다.

#### REQ-COLLAB-033 [Event-Driven] 원격 편집 수신
WHEN `edit_broadcast` 메시지를 수신하면 THEN `CollabMinutesNotifier`는 해당 필드 값을 갱신하고, UI에 변경을 알려야 한다(SHALL). 현재 사용자가 편집 중인 필드는 덮어쓰지 않아야 한다(SHALL NOT).

### 4.5 UI Integration

#### REQ-COLLAB-040 [Ubiquitous] _MinutesTab 확장
`_MinutesTab`은 `CollabMinutesNotifier`를 구독하여 편집 상태를 렌더링해야 한다(SHALL). 기존 `_editedSections` 로컬 상태를 `CollabMinutesState.fields`로 교체한다.

#### REQ-COLLAB-041 [Event-Driven] 실시간 편집 반영
WHEN 다른 사용자의 편집이 수신되면 THEN 해당 셀에 변경 내용을 즉시 표시해야 한다(SHALL). 현재 사용자가 편집 중인 셀은 편집 완료 시까지 원격 변경을 보류하고, 완료 후 LWW를 적용해야 한다(SHALL).

#### REQ-COLLAB-042 [Ubiquitous] Presence 표시
시스템은 현재 편집 세션에 참여 중인 사용자 목록을 회의록 상단에 표시해야 한다(SHALL). 각 사용자는 고유한 색상 아바타로 구분되며, 활성 편집 중인 필드를 표시해야 한다(SHALL).

#### REQ-COLLAB-043 [State-Driven] 협업 모드 진입
IF 회의록이 팀에 공유되어 있고 사용자에게 편집 권한(member 이상)이 있으면 THEN 사용자는 "공동 편집" 버튼을 통해 협업 세션에 참여할 수 있다(SHALL).

### 4.6 Security

#### REQ-COLLAB-050 [UnwantedBehaviour] 미인증 WebSocket 접근 차단
시스템은 JWT 토큰 없이 WebSocket 연결을 시도하면 즉시 연결을 거부해야 한다(SHALL NOT accept).

#### REQ-COLLAB-051 [UnwantedBehaviour] 권한 없는 편집 차단
시스템은 viewer 역할의 사용자가 `edit` 메시지를 전송하면 이를 무시하고 `error` 메시지를 반환해야 한다(SHALL NOT accept). viewer는 `sync_state`와 `user_joined`/`user_left`만 수신할 수 있다(SHALL).

#### REQ-COLLAB-052 [Ubiquitous] Rate Limiting
시스템은 WebSocket 메시지에 대해 사용자당 초당 최대 10개의 `edit` 메시지를 허용해야 한다(SHALL). 초과 시 `rate_limited` 에러 메시지를 반환하고 1초간 해당 사용자의 메시지를 무시해야 한다(SHALL).

#### REQ-COLLAB-053 [UnwantedBehaviour] 세션 하이재킹 방지
시스템은 WebSocket 연결 시 사용자가 해당 task_id의 팀 멤버인지 확인해야 한다(SHALL NOT allow non-members). 팀에 속하지 않은 사용자의 연결은 4004 코드로 거부해야 한다(SHALL).

## 5. 제외 항목 (Non-Goals)

| 항목 | 이유 |
|------|------|
| 버전 히스토리 및 복구 | 인터뷰 결정, 후속 SPEC으로 분리. MinutesVersion 모델은 존재하나 본 SPEC에서 미사용 |
| CRDT (Yjs/Automerge) | 2~5명 소규모 환경에서 오버엔지니어링, LWW로 충분 |
| 댓글/코멘트 기능 | 후속 기능, 본 SPEC 범위 외 |
| 오프라인 편집 | WebSocket 연결 필요, 오프라인 시 로컬 편집은 기존 휘발성 동작 유지 |
| 커서 위치 동기화 | 인터뷰에서 "커서 표시" 언급되었으나, 셀 단위 편집 UI에서 커서 개념 불필요. 대신 "편집 중인 필드"로 대체 |
| 이미지/파일 첨부 편집 | 텍스트 필드 편집만 지원 |
| 섹션/행 추가/삭제 | 인터뷰에서 "섹션 추가/수정/삭제" 언급되었으나, 기존 테이블 구조 변경은 위험. 첫 버전은 기존 필드 편집만 지원 |

## 6. 영향 받는 파일 (Affected Files)

### 6.1 신규 파일

| 파일 경로 | 용도 |
|-----------|------|
| `backend/app/api/v1/collaboration/collab.py` | WebSocket 엔드포인트 + ConnectionManager |
| `backend/services/collab_service.py` | 협업 편집 비즈니스 로직 (LWW, room 관리) |
| `backend/schemas/collab.py` | WebSocket 메시지 Pydantic 스키마 |
| `client/lib/services/collab_socket_service.dart` | WebSocket 클라이언트 서비스 |
| `client/lib/providers/collab_minutes_provider.dart` | Riverpod AsyncNotifier + 상태 모델 |
| `client/lib/widgets/collab_presence_bar.dart` | Presence 표시 위젯 |
| `client/lib/widgets/collab_editing_indicator.dart` | 셀 편집 중 표시 위젯 |

### 6.2 수정 파일 (Brownfield Delta)

| 파일 경로 | 변경 유형 | 설명 |
|-----------|-----------|------|
| `backend/app/api/v1/minutes/minutes.py` | **[DELTA: 추가]** | `PATCH /minutes/{task_id}` 엔드포인트 추가 |
| `backend/app/api/v1/collaboration/__init__.py` | **[DELTA: 수정]** | collab 라우터 등록 |
| `client/lib/screens/result_screen.dart` | **[DELTA: 수정]** | `_MinutesTab`에 CollabMinutesNotifier 연동, `_editedSections` → 상태 구독으로 교체 |
| `client/pubspec.yaml` | **[DELTA: 추가]** | `web_socket_channel: ^3.0.0` 의존성 추가 |

## 7. 메시지 프로토콜

### 7.1 클라이언트 → 서버

| type | 용도 | 필드 |
|------|------|------|
| `edit` | 필드 편집 | `field`, `value`, `timestamp` |
| `cursor` | 편집 중인 필드 알림 | `field` (편집 시작 시) 또는 `null` (편집 종료 시) |
| `ping` | 하트비트 응답 | 없음 |

### 7.2 서버 → 클라이언트

| type | 용도 | 필드 |
|------|------|------|
| `sync_state` | 전체 상태 동기화 | `fields`, `last_editors`, `timestamps` |
| `edit_broadcast` | 원격 편집 알림 | `field`, `value`, `user_id`, `server_timestamp` |
| `user_joined` | 참여자 입장 | `user_id`, `display_name`, `color` |
| `user_left` | 참여자 퇴장 | `user_id` |
| `cursor_broadcast` | 타 사용자 편집 필드 | `user_id`, `field` |
| `error` | 에러 알림 | `code`, `message` |
| `pong` | 하트비트 응답 | 없음 |
| `rate_limited` |Rate limit 초과 | `retry_after_ms` |

### 7.3 에러 코드

| 코드 | 의미 |
|------|------|
| 4001 | 인증 실패 (JWT 무효/만료) |
| 4003 | Room 정원 초과 (최대 5명) |
| 4004 | 권한 없음 (팀 멤버 아님) |
| 4005 | 편집 권한 없음 (viewer 역할) |

## 8. 성능 목표

| 지표 | 목표값 | 측정 방법 |
|------|--------|-----------|
| 편집 → 브로드캐스트 지연 | < 1초 (P95) | 클라이언트 타임스탬프 비교 |
| WebSocket 연결 수립 | < 500ms | 네트워크 타임아웃 측정 |
| Room 당 메모리 | < 1MB | 프로파일링 |
| 동시 Room 수 | 최대 10개 | 서버 메모리 기준 |
| DB 영속화 지연 | < 3초 | Redis → DB 타임스탬프 비교 |
