# Plan: SPEC-COLLAB-001 — 회의록 실시간 공동 편집

## 1. 구현 전략

### 1.1 접근법: Bottom-Up (인프라 → 서비스 → UI)

WebSocket 인프라가 모든 것의 기반이 되므로, 백엔드 인프라를 먼저 구축하고 서비스 로직, Flutter 클라이언트, UI 통합 순서로 진행한다. 각 마일스톤은 독립적으로 검증 가능하다.

### 1.2 기존 패턴 준수

| 패턴 | 참조 | 본 SPEC 적용 |
|------|------|-------------|
| Router 구조 | `backend/app/api/v1/{domain}/{feature}.py` | `collaboration/collab.py` |
| 서비스 계층 | `backend/services/{domain}_service.py` | `services/collab_service.py` |
| Pydantic 스키마 | `backend/schemas/*.py` | `schemas/collab.py` |
| Riverpod AsyncNotifier | `client/lib/providers/*.dart` | `collab_minutes_provider.dart` |
| SSE 수명 관리 | `ProcessingScreen` initState/dispose | `CollabSocketService` connect/disconnect |
| JWT 검증 | `get_current_user` dependency | WebSocket 쿼리 파라미터에서 토큰 추출 후 동일 검증 |

### 1.3 기술 스택

| 계층 | 기술 | 버전 |
|------|------|------|
| Backend WebSocket | FastAPI WebSocket (내장) | 0.135+ |
| Backend 검증 | Pydantic | 2.9+ |
| Redis Pub/Sub | redis.asyncio | 기존 |
| Flutter WebSocket | web_socket_channel | ^3.0.0 (신규 추가) |
| Flutter 상태관리 | Riverpod | 2.6.1 (기존) |

## 2. 마일스톤

### Milestone 1: Backend WebSocket 인프라 (M1)

**목표:** JWT 인증 WebSocket 서버, ConnectionManager, Room 관리 구현

**신규 파일:**
- `backend/app/api/v1/collaboration/collab.py` — WebSocket 엔드포인트
- `backend/schemas/collab.py` — 메시지 스키마

**수정 파일:**
- `backend/app/api/v1/collaboration/__init__.py` [DELTA] — collab 라우터 등록

**작업 항목:**
1. `CollabMessage` Pydantic 스키마 정의 (유니온 타입: edit, cursor, ping)
2. `CollabConnectionManager` 클래스 구현
   - `connect(task_id, user_id, websocket)`: room 참가, 최대 5명 제한
   - `disconnect(task_id, user_id)`: room 퇴장, user_left 브로드캐스트
   - `broadcast(task_id, message, exclude_user)`: room 내 브로드캐스트
   - `send_to_user(user_id, message)`: 개별 전송
3. WebSocket 엔드포인트 `WS /api/v1/collab/{task_id}/ws`
   - 쿼리 파라미터에서 JWT 추출 → `AuthService.decode_access_token()` 검증
   - 팀 멤버십 확인 (task_id → team_id → TeamMember 존재 여부)
   - 연결 수립 후 `sync_state` 전송
   - 메시지 루프: edit/cursor/ping 핸들링
   - 하트비트: 30초 ping, 60초 타임아웃
4. Room 기반 presence 관리 (user_joined, user_left 이벤트)
5. 단위 테스트: ConnectionManager, JWT 검증, Room 제한

**검증:** `pytest backend/tests/unit/test_collab_connection.py` 통과

### Milestone 2: Collaborative Editing Service (M2)

**목표:** Per-field LWW 충돌 해결, Redis 상태 관리, DB 영속화

**신규 파일:**
- `backend/services/collab_service.py` — 편집 비즈니스 로직

**수정 파일:**
- `backend/app/api/v1/minutes/minutes.py` [DELTA] — PATCH 엔드포인트 추가

**작업 항목:**
1. `CollabService` 클래스 구현
   - `apply_edit(task_id, field, value, user_id)` → LWW 적용
   - `get_state(task_id)` → Redis에서 전체 상태 조회
   - `persist_to_db(task_id)` → Redis → TaskResult.result_data 병합 저장
   - `start_debounced_persist(task_id)` → 3초 디바운스 타이머
2. Per-field LWW 구현
   - Redis Hash `collab:state:{task_id}`에 field별 `{value, user_id, server_timestamp}` 저장
   - 서버 타임스탬프 기준 (단조 증가 보장)
   - 편집 시 Redis 즉시 갱신 + 브로드캐스트
3. Debounced DB 영속화
   - 마지막 저장 후 3초 경과 시 자동 persist
   - 마지막 참여자 퇴장 시 즉시 persist
   - persist 시 `TaskResult.result_data` JSON을 편집된 필드로 부분 업데이트
4. `PATCH /api/v1/minutes/{task_id}` 엔드포인트
   - `fields: dict[str, str]` 부분 업데이트
   - `get_current_user` 의존성으로 인증
   - Redis 캐시 갱신
5. 통합 테스트: LWW 충돌 시나리오, DB 영속화

**검증:** `pytest backend/tests/integration/test_collab_service.py` 통과

### Milestone 3: Flutter WebSocket Client (M3)

**목표:** WebSocket 클라이언트 서비스와 Riverpod 상태 관리 구현

**신규 파일:**
- `client/lib/services/collab_socket_service.dart` — WebSocket 연결 관리
- `client/lib/providers/collab_minutes_provider.dart` — 상태 관리 + 메시지 핸들링

**수정 파일:**
- `client/pubspec.yaml` [DELTA] — `web_socket_channel: ^3.0.0` 추가

**작업 항목:**
1. `CollabSocketService` 클래스
   - `connect(taskId, token)`: WebSocket 연결 수립
   - `disconnect()`: 연결 종료 및 리소스 정리
   - `sendEdit(field, value)`: edit 메시지 전송
   - `sendCursor(field?)`: cursor 메시지 전송
   - `messages`: `Stream<CollabMessage>` (수신 메시지 스트림)
   - 지수 백오프 재연결 (1s → 2s → 4s → ... → 30s max)
   - 연결 상태 노출: `ConnectionState` enum
2. `CollabMinutesState` 모델
   - `fields: Map<String, String>` — 필드 값
   - `editingUsers: Map<String, String>` — field → userId
   - `activeUsers: Set<CollabUser>` — 접속 중 사용자
   - `isConnected: bool`
3. `CollabMinutesNotifier` (Riverpod AsyncNotifier)
   - `build(taskId)`: 초기 상태 로드 + WebSocket 연결
   - `editField(field, value)`: 로컬 상태 갱신 + WebSocket 전송
   - `startEditing(field)`: cursor 메시지 전송
   - `stopEditing()`: cursor(null) 메시지 전송
   - 메시지 수신 핸들러: edit_broadcast, user_joined, user_left, sync_state
   - dispose 시 WebSocket 연결 종료
4. Provider 정의
   - `collabMinutesProvider`: `AsyncNotifierProvider<CollabMinutesNotifier, CollabMinutesState>`
   - `collabConnectionStateProvider`: `StateProvider<ConnectionState>`
5. 단위 테스트: 메시지 파싱, 상태 갱신 로직

**검증:** `flutter test test/providers/collab_minutes_provider_test.dart` 통과

### Milestone 4: UI 통합 (M4)

**목표:** _MinutesTab에 협업 기능 통합, Presence 표시, 편집 인디케이터

**신규 파일:**
- `client/lib/widgets/collab_presence_bar.dart` — 참여자 목록 위젯
- `client/lib/widgets/collab_editing_indicator.dart` — 셀 편집 중 표시 위젯

**수정 파일:**
- `client/lib/screens/result_screen.dart` [DELTA] — _MinutesTab 확장

**작업 항목:**
1. `CollabPresenceBar` 위젯
   - 활성 사용자 아바타 목록 (고유 색상)
   - "N명 편집 중" 텍스트
   - 연결 상태 인디케이터 (녹색/회색 점)
2. `CollabEditingIndicator` 위젯
   - 다른 사용자가 편집 중인 셀에 사용자 이름/색상 표시
   - 편집 중 필드 하이라이트
3. `_MinutesTab` 수정
   - `_editedSections` 로컬 Map → `ref.watch(collabMinutesProvider)` 구독으로 교체
   - "공동 편집" 버튼 추가 (팀 공유 회의록에만 표시)
   - 셀 편집 다이얼로그에 편집 중 인디케이터 추가
   - 원격 편집 수신 시 즉시 셀 텍스트 갱신
   - 현재 편집 중인 필드는 원격 변경 보류 (편집 완료 후 LWW 적용)
4. 협업 세션 진입 흐름
   - 팀 공유 회의록 → "공동 편집" 버튼 → WebSocket 연결 → 실시간 동기화 시작
   - 비공유 회의록 → 기존 로컬 편집 동작 유지 (휘발성)
5. 에러 UX
   - 연결 끊김 시 스낵바 알림
   - 재연결 중 인디케이터
   - Rate limited 시 "잠시 후 다시 시도해주세요" 알림
6. 위젯 테스트: PresenceBar, EditingIndicator

**검증:** `flutter test test/widgets/collab_presence_bar_test.dart` 통과

### Milestone 5: 보안 강화 및 Rate Limiting (M5)

**목표:** WebSocket 보안 게이트, Rate Limiting, 권한 검증

**수정 파일:**
- `backend/app/api/v1/collaboration/collab.py` [DELTA] — 보안 로직 추가

**작업 항목:**
1. WebSocket 인증 강화
   - 연결 시 토큰 만료 확인 (15분 Access Token)
   - 토큰 만료 시 4001 코드 + 재연결 유도 메시지
2. 권한 게이팅
   - `edit` 메시지 수신 시 사용자 Role 확인
   - viewer → `error` 메시지 (code: 4005)
   - 팀 멤버 아님 → 연결 거부 (code: 4004)
3. Rate Limiting
   - 사용자당 초당 최대 10개 edit 메시지
   - 초과 시 `rate_limited` 메시지 반환 + 1초 무시
   - 메모리 기반 카운터 (per-connection state)
4. 입력 검증
   - field 이름 화이트리스트 검증 (기존 회의록 필드만 허용)
   - value 길이 제한 (최대 10,000자)
   - JSON 메시지 파싱 실패 시 `error` 응답
5. 보안 테스트: 미인증 접근, viewer 편집 시도, Rate Limit 초과

**검증:** `pytest backend/tests/unit/test_collab_security.py` 통과

### Milestone 6: 통합 테스트 및 E2E (M6)

**목표:** 전체 협업 플로우 검증

**작업 항목:**
1. 백엔드 통합 테스트
   - 다중 클라이언트 WebSocket 연결 시나리오
   - LWW 충돌 해결 검증 (동시 편집 시 서버 타임스탬프 기준)
   - Redis → DB 영속화 검증
   - 연결 끊김 및 재연결 시나리오
2. Flutter 위젯 테스트
   - CollabMinutesNotifier 상태 갱신
   - UI 반응성 (원격 편집 수신 시 즉시 갱신)
3. E2E 테스트 시나리오
   - 사용자 A 편집 → 사용자 B 화면에 1초 이내 반영
   - 3명 동시 편집 → LWW 충돌 해결
   - 사용자 퇴장 → presence 갱신
   - 네트워크 끊김 → 재연결 → 상태 동기화

**검증:** `pytest backend/tests/e2e/test_collab_e2e.py` 통과

## 3. 의존성 그래프

```
M1 (WebSocket 인프라)
 ├→ M2 (편집 서비스)
 │   ├→ M3 (Flutter 클라이언트)
 │   │   └→ M4 (UI 통합)
 │   └→ M5 (보안 강화)
 └→ M5 (보안 강화)
      └→ M6 (통합 테스트)
```

**병렬 가능:** M3과 M5는 M2 완료 후 병렬 진행 가능

## 4. 리스크 완화

| 리스크 | 영향 | 완화 전략 |
|--------|------|-----------|
| WebSocket 메모리 누수 | 서버 불안정 | 연결 종료 시 명시적 리소스 해제, ConnectionManager 정리 로직 |
| LWW 충돌 빈도 예상 초과 | 사용자 경험 저하 | 모니터링 메트릭 추가, 필요시 per-cell locking 도입 |
| Flutter WebSocket 웹 호환성 | 크로스 플랫폼 제약 | web_socket_channel 웹 지원 확인, WebSocketChannel.connect 사용 |
| JWT 토큰 만료 중 세션 유지 | 연결 끊김 | 토큰 갱신 시 WebSocket 재연결 또는 쿼리 파라미터 갱신 |
| Redis 채널 충돌 (SSE와) | 이벤트 오송 | 네임스페이스 분리: `sse:{task_id}` vs `collab:{task_id}` |

## 5. 파일 변경 요약

### 신규 (7개)
```
backend/app/api/v1/collaboration/collab.py     # M1
backend/services/collab_service.py              # M2
backend/schemas/collab.py                       # M1
client/lib/services/collab_socket_service.dart  # M3
client/lib/providers/collab_minutes_provider.dart # M3
client/lib/widgets/collab_presence_bar.dart     # M4
client/lib/widgets/collab_editing_indicator.dart # M4
```

### 수정 (4개)
```
backend/app/api/v1/minutes/minutes.py           # M2 [DELTA: PATCH 엔드포인트 추가]
backend/app/api/v1/collaboration/__init__.py    # M1 [DELTA: 라우터 등록]
client/lib/screens/result_screen.dart            # M4 [DELTA: _MinutesTab 확장]
client/pubspec.yaml                              # M3 [DELTA: web_socket_channel 추가]
```

## 6. 테스트 계획

| 마일스톤 | 테스트 파일 | 테스트 수 (예상) |
|-----------|-------------|-----------------|
| M1 | `backend/tests/unit/test_collab_connection.py` | 12 |
| M2 | `backend/tests/integration/test_collab_service.py` | 10 |
| M3 | `client/test/providers/collab_minutes_provider_test.dart` | 8 |
| M4 | `client/test/widgets/collab_presence_bar_test.dart` | 6 |
| M5 | `backend/tests/unit/test_collab_security.py` | 10 |
| M6 | `backend/tests/e2e/test_collab_e2e.py` | 8 |
| **총합** | | **54** |

## 7. 예상 공수

| 마일스톤 | 예상 시간 | 난이도 |
|-----------|-----------|--------|
| M1 | 3h | 중 |
| M2 | 2.5h | 중 |
| M3 | 3h | 중 |
| M4 | 3h | 중 |
| M5 | 1.5h | 낮음 |
| M6 | 2h | 중 |
| **총합** | **15h** | |
