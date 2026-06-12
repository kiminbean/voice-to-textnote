# Research: 회의록 실시간 공동 편집 (SPEC-COLLAB-001)

## 1. 아키텍처 분석

### 1.1 기존 실시간 인프라 (SSE)

**SSE 엔드포인트**: `GET /api/v1/tasks/{task_id}/stream` (`backend/app/api/v1/transcription/stream.py`)
- `sse_starlette` 라이브러리 사용, `EventSourceResponse` 반환
- Redis Pub/Sub 기반: `subscribe_task_events(redis_client, task_id)` 이벤트 구독
- 15초 heartbeat ping, completed/failed 시 자동 종료
- **상태 전용(processing progress)** — 문서 편집에는 사용 불가

**Flutter SSE 클라이언트**: `client/lib/services/sse_service.dart`
- `http.Client` 기반 (Dio 아님), `X-API-Key` 헤더로 인증
- `Stream<Map<String, dynamic>> connect(taskId)` 패턴
- ProcessingScreen에서 initState/dispose로 수명 관리

**WebSocket 인프라**: **존재하지 않음**
- `backend/`에 WebSocket 핸들러, ConnectionManager 없음
- `pubspec.yaml`에 `web_socket_channel` 미포함
- 전적으로 새로 구축 필요

### 1.2 회의록 데이터 모델

**백엔드**: `TaskResult` 모델 (`backend/db/models.py`)
- `result_data` (JSON)에 전체 회의록 저장 (segments, speakers, markdown)
- Redis 캐시: `task:min:result:{task_id}` (24h TTL)
- **회의록 수정(PUT/PATCH) API 없음** — MinutesApi는 create/getStatus/getResult/delete만 제공

**Flutter**: `_MinutesTab` (`result_screen.dart` L966-1713+)
- `Map<String, String> _editedSections`에 셀 단위 편집 저장
- **휘발성 상태** — 화면 dispose 시 편집 내용 손실
- 테이블 레이아웃: `_buildDynamicTable`(템플릿 기반) 또는 `_buildMinutesTable`(고정 7행)
- 셀 편집: `_editCell(label, value)` → TextField 다이얼로그

**버전 관리**: `MinutesVersion` 모델 (`backend/db/version_models.py`) — 이미 존재
- `task_id` 기준으로 version_number 단조 증가
- `content` JSON 스냅샷, `author_id`, `change_summary`
- API: `POST/GET/DELETE /minutes/{task_id}/versions` (CRUD + diff)

### 1.3 인증 및 RBAC

**JWT 인증** (`backend/app/dependencies.py` → `get_current_user`):
- `Authorization: Bearer <token>` 헤더 검증
- `AuthService.decode_access_token()` → `payload.sub` = user UUID
- 15분 Access Token + 7일 Refresh Token Rotation

**RBAC** (`backend/db/auth_models.py`):
- `TeamMember.role`: admin / member / viewer
- `MeetingOwnership`: task_id ↔ owner_id + team_id 매핑
- viewer → 읽기 전용, member 이상 → 편집 권한 (자연스러운 매핑)

**Flutter 인증**:
- `AuthNotifier` (StateNotifier<AuthState>) + `AuthService` (flutter_secure_storage)
- `_AuthInterceptor` (Dio)가 자동으로 `Bearer <token>` 부착
- **WebSocket은 Dio 인터셉터 사용 불가** → 수동 토큰 주입 필요

### 1.4 팀 공유 (기존 협업 기반)

**백엔드**: `collaboration/meetings.py` — share/unshare/list
**Flutter**: `team_share_dialog.dart`, `TeamApi.shareMeeting(taskId, teamId)`
- 공유된 회의록은 팀 멤버가 조회 가능
- 공동 편집을 위한 자연스러운 진입점

## 2. 기존 패턴 및 관례

### 2.1 백엔드 패턴
- **Router 구조**: `backend/app/api/v1/{domain}/{feature}.py` + `registry.py` 자동 등록
- **의존성 주입**: `Depends(get_redis_client)`, `Depends(get_db_session)`, `Depends(get_current_user)`
- **서비스 계층**: `backend/services/{domain}_service.py` (비즈니스 로직)
- **에러 처리**: `backend/app/errors.py` 헬퍼 (not_found, forbidden 등)
- **비동기**: 전적으로 async/await, SQLAlchemy async 세션

### 2.2 Flutter 패턴
- **상태 관리**: Riverpod (flutter_riverpod 2.6.1)
  - `AsyncNotifier<T>` for mutable state
  - `FutureProvider.family<T, K>` for one-shot loads
- **API 계층**: Provider 주입 `dioProvider` → domain API classes
- **화면 수명**: initState에서 구독, dispose에서 해제

## 3. 리스크 및 제약사항

### 3.1 기술적 제약
- Apple Silicon Mac에서 동시 STT 처리 시 메모리 제약 (6GB/모델)
- WebSocket 연결 당 메모리 점유 고려 필요 (2-5명 소규모로 완화)
- Redis Pub/Sub은 이미 SSE에서 사용 중 — 채널 네임스페이스 분리 필요

### 3.2 아키텍처 리스크
- **충돌 해결**: 소규모(2-5명) + 테이블 셀 단위 편집 → LWW(Last-Write-Wins) 적합
  - `_editedSections`가 이미 키(label)별로 구조화 → per-field LWW 가능
  - CRDT(Yjs/Automerge)는 오버엔지니어링 가능성
- **지속성**: 현재 `_editedSections`가 휘발성 → 백엔드 저장 API 필수
- **버전 관리**: `MinutesVersion` 모델이 이미 존재하나, 인터뷰에서 "버전 히스토리/복구 제외" 결정

### 3.3 보안 고려사항
- WebSocket 인증: HTTP 헤더 불가 → 쿼리 파라미터 또는 첫 메시지로 JWT 전달
- 세션 하이재킹 방지: 연결 시 사용자 검증 + meeting_id 권한 확인
- Rate limiting: WebSocket 메시지에도 적용 필요 (과도한 편집 이벤트)

## 4. 권장 구현 접근법

### 4.1 기술 선택
- **WebSocket**: FastAPI 네이티브 `WebSocket` 지원 (별도 라이브러리 불필요)
- **충돌 해결**: Per-field LWW with Lamport timestamp
  - 각 셀(label) 단위로 `{value, timestamp, userId}` 관리
  - 서버가 중앙 타임스탬프 발급 (단순하고 신뢰 가능)
- **Flutter WebSocket**: `web_socket_channel` 패키지 추가

### 4.2 아키텍처 제안
```
Flutter Client                    Backend
┌──────────────┐     WebSocket    ┌──────────────────────┐
│ CollabSocket │◄─────────────────►│ CollabRouter         │
│ Service      │  JWT auth on     │  ├─ ConnectionMgr    │
│              │  connect         │  ├─ JWT validation   │
│ CollabMinute │                  │  └─ Room management  │
│ Notifier     │                  │                      │
│ (Riverpod)   │                  │ CollabService        │
└──────────────┘                  │  ├─ Apply edits      │
                                  │  ├─ Broadcast ops    │
                                  │  └─ Persist to DB    │
                                  │                      │
                                  │ Redis Pub/Sub        │
                                  │  └─ collab:{task_id} │
                                  └──────────────────────┘
```

### 4.3 통합 앵커
- **문서 ID**: `Meeting.minutesTaskId` (또는 `task_results.task_id`)
- **편집 단위**: `_editedSections` 키(label) = per-field 단위
- **권한**: `TeamMember.role` (viewer → 읽기 전용)
- **새 Provider**: `collabMinutesProvider` (AsyncNotifier)
- **WS 수명 관리**: ProcessingScreen SSE 패턴 복제 (initState/dispose)

## 5. 참조 구현 (내부 코드베이스)

| 기능 | 파일 | 설명 |
|------|------|------|
| SSE 스트리밍 | `backend/app/api/v1/transcription/stream.py` | Redis Pub/Sub → SSE 패턴 |
| SSE 클라이언트 | `client/lib/services/sse_service.dart` | Stream 기반 연결/해제 |
| 인증 의존성 | `backend/app/dependencies.py:get_current_user` | JWT 검증 패턴 |
| RBAC 모델 | `backend/db/auth_models.py:TeamMember` | role 기반 권한 |
| 버전 관리 | `backend/db/version_models.py:MinutesVersion` | 콘텐츠 스냅샷 (참고용, 본 SPEC에서는 제외) |
| 회의 공유 | `backend/app/api/v1/collaboration/meetings.py` | 팀 공유 패턴 |
| 편집 UI | `client/lib/screens/result_screen.dart:_MinutesTab` | 셀 편집 진입점 |
