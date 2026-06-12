# Acceptance Criteria: SPEC-COLLAB-001 — 회의록 실시간 공동 편집

## 1. WebSocket 연결 관리 (REQ-COLLAB-001 ~ 004)

### AC-001: JWT 인증 WebSocket 연결

**Given** 유효한 JWT Access Token을 가진 사용자가 있고
**And** 해당 사용자가 task_id의 팀 멤버이다
**When** `WS /api/v1/collab/{task_id}/ws?token=<jwt>`로 연결을 시도하면
**Then** WebSocket 연결이 성공적으로 수립된다
**And** `sync_state` 메시지가 즉시 전송된다

### AC-002: JWT 없는 연결 거부

**Given** JWT 토큰 없이
**When** `WS /api/v1/collab/{task_id}/ws`로 연결을 시도하면
**Then** 4001 코드로 연결이 즉시 거부된다
**And** WebSocket 연결이 수립되지 않는다

### AC-003: 만료된 토큰 거부

**Given** 만료된 JWT Access Token으로
**When** WebSocket 연결을 시도하면
**Then** 4001 코드로 연결이 거부된다

### AC-004: Room 최대 인원 제한

**Given** task_id A의 room에 이미 5명이 접속해 있고
**When** 6번째 사용자가 같은 room에 연결을 시도하면
**Then** 4003 코드로 연결이 거부된다
**And** 기존 5명의 연결에 영향이 없다

### AC-005: 하트비트 연결 유지

**Given** WebSocket 연결이 활성 상태이고
**When** 서버가 30초마다 ping을 전송하면
**Then** 클라이언트는 pong으로 응답해야 한다
**And** 60초 이내 pong 응답이 없으면 연결이 종료된다

---

## 2. 실시간 편집 동기화 (REQ-COLLAB-010 ~ 013)

### AC-010: 단일 편집 브로드캐스트

**Given** 사용자 A와 B가 같은 room에 접속해 있고
**When** 사용자 A가 `edit` 메시지로 `summary_text` 필드를 "새 요약"으로 편집하면
**Then** 사용자 B가 `edit_broadcast` 메시지를 수신한다
**And** 메시지의 `field`는 `summary_text`, `value`는 "새 요약"이다
**And** 사용자 A는 `edit_broadcast`를 수신하지 않는다 (자신의 편집은 제외)

### AC-011: LWW 충돌 해결

**Given** 사용자 A와 B가 같은 room에 있고
**And** `summary_text` 필드의 현재 값이 "원본"이다
**When** 사용자 A가 "A 수정"을, 사용자 B가 "B 수정"을 거의 동시에(100ms 이내) 전송하면
**Then** 서버 타임스탬프가 더 늦은 편집이 승자가 된다
**And** 두 사용자 모두 동일한 최종 값을 수신한다

### AC-012: 신규 참여자 상태 동기화

**Given** 사용자 A가 이미 편집 중이고 `summary_text` = "수정됨" 상태이고
**When** 사용자 B가 room에 입장하면
**Then** 사용자 B가 `sync_state` 메시지를 수신한다
**And** `sync_state.fields["summary_text"]` = "수정됨"이다
**And** `sync_state`에 모든 필드의 현재 값이 포함되어 있다

### AC-013: 독립 필드 편집

**Given** 사용자 A가 `summary_text`를 편집하고
**When** 사용자 B가 `action_items`를 편집하면
**Then** 두 편집 모두 독립적으로 적용된다
**And** 한 필드의 편집이 다른 필드에 영향을 주지 않는다

---

## 3. 영속화 (REQ-COLLAB-020 ~ 022)

### AC-020: Redis 즉시 저장

**Given** 협업 세션이 활성 상태이고
**When** 사용자가 `edit` 메시지를 전송하면
**Then** Redis `collab:state:{task_id}`에 변경 사항이 즉시 반영된다
**And** 후속 `sync_state` 요청에 새 값이 포함된다

### AC-021: 디바운스 DB 영속화

**Given** 마지막 DB 저장 후 3초가 경과했고
**And** Redis에 미저장 편집이 있다
**When** 디바운스 타이머가 트리거되면
**Then** `TaskResult.result_data`가 Redis의 최신 값으로 업데이트된다
**And** `PATCH /api/v1/minutes/{task_id}` API로 동일한 결과를 조회할 수 있다

### AC-022: 세션 종료 시 영속화

**Given** room에 1명의 사용자만 남아 있고
**And** 미저장 편집이 있다
**When** 마지막 사용자가 퇴장하면
**Then** DB에 즉시 영속화가 수행된다
**And** `GET /api/v1/minutes/{task_id}` 결과에 편집 내용이 반영된다

### AC-023: PATCH API 직접 호출

**Given** 인증된 사용자가 있고
**When** `PATCH /api/v1/minutes/{task_id}`로 `{"fields": {"summary_text": "직접 수정"}}`을 전송하면
**Then** 200 OK 응답을 받는다
**And** Redis 캐시가 갱신된다
**And** 후속 GET 요청에 수정된 값이 반영된다

---

## 4. Flutter 클라이언트 (REQ-COLLAB-030 ~ 033)

### AC-030: WebSocket 연결 수립

**Given** Flutter 클라이언트에 유효한 JWT 토큰이 있고
**When** `CollabSocketService.connect(taskId, token)`을 호출하면
**Then** WebSocket 연결이 수립된다
**And** `CollabMinutesState.isConnected`가 `true`가 된다

### AC-031: 자동 재연결

**Given** WebSocket 연결이 활성 상태이고
**When** 네트워크 끊김으로 연결이 종료되면
**Then** 1초 후 첫 재연결을 시도한다
**And** 실패 시 2초, 4초 간격으로 재시도한다
**And** 최대 30초 간격까지 백오프한다
**And** 재연결 성공 시 `sync_state`로 최신 상태를 수신한다

### AC-032: 로컬 편집 전송

**Given** CollabMinutesNotifier가 연결되어 있고
**When** 사용자가 `editField("summary_text", "새 내용")`을 호출하면
**Then** 로컬 상태 `fields["summary_text"]`가 즉시 "새 내용"으로 갱신된다
**And** `edit` 메시지가 WebSocket으로 전송된다

### AC-033: 원격 편집 수신 시 상태 갱신

**Given** 사용자 A가 `summary_text`를 편집 중이지 않고
**When** `edit_broadcast` 메시지로 `action_items` 필드 변경을 수신하면
**Then** `CollabMinutesState.fields["action_items"]`가 갱신된다
**And** UI에 변경 사항이 즉시 반영된다

### AC-034: 편집 중 필드 보호

**Given** 사용자 A가 `summary_text` 필드를 편집 중이고 (TextField 포커스 활성)
**When** 원격 `edit_broadcast`로 `summary_text` 변경이 수신되면
**Then** 로컬 편집이 우선하여 보존된다
**And** 사용자 A가 편집을 완료(포커스 해제)하면 LWW가 적용된다

---

## 5. UI 통합 (REQ-COLLAB-040 ~ 043)

### AC-040: _MinutesTab 상태 구독

**Given** 협업 세션이 활성 상태이고
**When** `_MinutesTab`이 렌더링되면
**Then** 셀 값이 `CollabMinutesState.fields`에서 읽혀진다
**And** 기존 `_editedSections` 로컬 Map은 사용되지 않는다

### AC-041: 실시간 편집 반영

**Given** 사용자 A와 B가 같은 회의록을 보고 있고
**When** 사용자 B가 "핵심 결정사항" 셀을 "새 결정"으로 편집하면
**Then** 사용자 A의 화면에서 해당 셀이 1초 이내에 "새 결정"으로 갱신된다

### AC-042: Presence 표시

**Given** 3명의 사용자가 같은 room에 접속해 있고
**When** 회의록 화면을 열면
**Then** 화면 상단에 3명의 사용자 아바타가 고유 색상으로 표시된다
**And** "3명 편집 중" 텍스트가 표시된다

### AC-043: 편집 중 표시

**Given** 사용자 A가 "액션 아이템" 셀을 편집 중이고
**When** 사용자 B가 같은 화면을 보면
**Then** "액션 아이템" 셀에 사용자 A의 색상과 이름이 표시된다
**And** 해당 셀에 시각적 하이라이트가 있다

### AC-044: 공동 편집 진입

**Given** 회의록이 팀에 공유되어 있고
**And** 사용자에게 편집 권한(member 이상)이 있다
**When** 회의록 화면을 열면
**Then** "공동 편집" 버튼이 표시된다
**And** 버튼 클릭 시 WebSocket 연결이 수립되고 실시간 동기화가 시작된다

### AC-045: 비공유 회의록 동작 유지

**Given** 회의록이 팀에 공유되어 있지 않고
**When** 회의록 화면을 열면
**Then** "공동 편집" 버튼이 표시되지 않는다
**And** 기존 로컬 편집 동작(_editedSections)이 그대로 유지된다

---

## 6. 보안 (REQ-COLLAB-050 ~ 053)

### AC-050: 미인증 접근 차단

**Given** JWT 토큰 없이
**When** WebSocket 연결을 시도하면
**Then** 연결이 거부된다 (code: 4001)
**And** 서버 로그에 인증 실패가 기록된다

### AC-051: Viewer 편집 차단

**Given** viewer 역할의 사용자가 WebSocket에 연결되어 있고
**When** `edit` 메시지를 전송하면
**Then** 서버가 `error` 메시지를 반환한다 (code: 4005)
**And** 다른 참여자에게 변경 사항이 브로드캐스트되지 않는다
**And** viewer는 `sync_state`, `user_joined`, `user_left`는 정상 수신한다

### AC-052: Rate Limiting

**Given** 사용자가 1초 이내에 10개의 `edit` 메시지를 전송하고
**When** 11번째 메시지를 전송하면
**Then** `rate_limited` 메시지가 반환된다
**And** `retry_after_ms` 필드에 대기 시간이 포함된다
**And** 1초간 해당 사용자의 메시지가 무시된다

### AC-053: 비팀원 접근 차단

**Given** 사용자가 task_id의 팀에 속하지 않고
**When** WebSocket 연결을 시도하면
**Then** 4004 코드로 연결이 거부된다
**And** 기존 room 참여자에게 영향이 없다

---

## 7. 성능 검증

### AC-P01: 편집 전파 지연

**Given** 2명의 사용자가 같은 room에 접속해 있고
**When** 한 사용자가 편집을 전송하면
**Then** 다른 사용자에게 1초(P95) 이내에 `edit_broadcast`가 도달한다

### AC-P02: Room 메모리

**Given** 5명의 사용자가 하나의 room에 접속해 있고
**When** 서버 메모리를 측정하면
**Then** Room당 메모리 점유가 1MB 미만이다

### AC-P03: 다중 Room 지원

**Given** 10개의 서로 다른 room이 활성 상태이고
**When** 각 room에서 독립적인 편집이 발생하면
**Then** Room 간 간섭 없이 독립적으로 동작한다

---

## 8. 에러 시나리오

### AC-E01: 서버 재시작 시 복구

**Given** 협업 세션이 활성 상태이고
**When** 서버가 재시작되면
**Then** 모든 WebSocket 연결이 종료된다
**And** 클라이언트는 지수 백오프로 재연결을 시도한다
**And** 서버 복구 후 재연결 시 `sync_state`로 상태가 복원된다
**And** 서버 재시작 전 Redis에 저장된 편집 내용이 보존된다

### AC-E02: 잘못된 메시지 형식

**Given** WebSocket 연결이 활성 상태이고
**When** JSON 파싱 실패하는 메시지를 수신하면
**Then** `error` 메시지를 반환한다
**And** 연결은 유지된다

### AC-E03: 존재하지 않는 필드 편집

**Given** WebSocket 연결이 활성 상태이고
**When** 존재하지 않는 field 이름으로 `edit` 메시지를 전송하면
**Then** `error` 메시지를 반환한다
**And** 다른 참여자에게 브로드캐스트되지 않는다

---

## 검증 체크리스트

- [ ] AC-001 ~ AC-005: WebSocket 연결 관리 (5개)
- [ ] AC-010 ~ AC-013: 실시간 편집 동기화 (4개)
- [ ] AC-020 ~ AC-023: 영속화 (4개)
- [ ] AC-030 ~ AC-034: Flutter 클라이언트 (5개)
- [ ] AC-040 ~ AC-045: UI 통합 (6개)
- [ ] AC-050 ~ AC-053: 보안 (4개)
- [ ] AC-P01 ~ AC-P03: 성능 (3개)
- [ ] AC-E01 ~ AC-E03: 에러 시나리오 (3개)
- [ ] **총 34개 Acceptance Criteria**
