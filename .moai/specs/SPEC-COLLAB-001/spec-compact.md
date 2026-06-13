# SPEC-COLLAB-001 Compact — 회의록 실시간 공동 편집

## 요구사항 (REQ)

### Backend WebSocket Server
- **REQ-COLLAB-001** [Ubiquitous] `WS /api/v1/collab/{task_id}/ws?token=<jwt>` 연결 제공. JWT 검증, 무효 시 4001 거부
- **REQ-COLLAB-002** [Ubiquitous] task_id 기준 room 관리, 최대 5명, 초과 시 4003 거부
- **REQ-COLLAB-003** [Event-Driven] user_joined/user_left 이벤트 브로드캐스트 (user_id, display_name 포함)
- **REQ-COLLAB-004** [Ubiquitous] 30초 ping/pong 하트비트, 60초 타임아웃 시 연결 종료

### Collaborative Editing Service
- **REQ-COLLAB-010** [Event-Driven] edit 메시지 수신 → per-field LWW 적용 → edit_broadcast 브로드캐스트
- **REQ-COLLAB-011** [State-Driven] 서버 타임스탬프 기준 LWW 충돌 해결
- **REQ-COLLAB-012** [Event-Driven] 신규 입장 시 sync_state 전송 (모든 필드 값, 수정자, 타임스탬프)
- **REQ-COLLAB-013** [Ubiquitous] 편집 단위 = 개별 셀(필드), 필드 간 독립성 보장

### Persistence Layer
- **REQ-COLLAB-020** [Event-Driven] 편집 시 Redis 즉시 반영, 3초 이내 DB 비동기 영속화
- **REQ-COLLAB-021** [Ubiquitous] Redis `collab:state:{task_id}` JSON 저장, TTL 1시간
- **REQ-COLLAB-022** [State-Driven] 3초 경과 또는 마지막 참여자 퇴장 시 Redis → TaskResult.result_data 병합

### Flutter WebSocket Client
- **REQ-COLLAB-030** [Ubiquitous] CollabSocketService (web_socket_channel 기반), 지수 백오프 재연결
- **REQ-COLLAB-031** [Ubiquitous] CollabMinutesNotifier (Riverpod AsyncNotifier), CollabMinutesState 관리
- **REQ-COLLAB-032** [Event-Driven] 셀 편집 완료 시 edit 메시지 WebSocket 전송
- **REQ-COLLAB-033** [Event-Driven] edit_broadcast 수신 시 필드 갱신, 편집 중 필드는 덮어쓰지 않음

### UI Integration
- **REQ-COLLAB-040** [Ubiquitous] _editedSections → CollabMinutesState.fields 교체
- **REQ-COLLAB-041** [Event-Driven] 원격 편집 즉시 표시, 편집 중 셀은 완료 후 LWW 적용
- **REQ-COLLAB-042** [Ubiquitous] 참여자 Presence 바 (고유 색상 아바타, 활성 편집 필드 표시)
- **REQ-COLLAB-043** [State-Driven] 팀 공유 + member 이상 권한 시 "공동 편집" 버튼 활성화

### Security
- **REQ-COLLAB-050** [UnwantedBehaviour] JWT 없는 WS 접근 즉시 거부
- **REQ-COLLAB-051** [UnwantedBehaviour] viewer edit 시 error(4005) 반환, sync_state/join/left만 수신
- **REQ-COLLAB-052** [Ubiquitous] 사용자당 초당 10 edit 제한, 초과 시 rate_limited 메시지
- **REQ-COLLAB-053** [UnwantedBehaviour] 비팀원 WS 접근 4004 거부

## 수용 기준 (AC) — 주요 시나리오

- AC-010: A 편집 → B에게 edit_broadcast 수신, A는 수신 안 함
- AC-011: 동시 편집 시 서버 타임스탬프 LWW로 동일 최종값 보장
- AC-012: 신규 참여자 sync_state로 현재 상태 즉시 수신
- AC-022: 마지막 참여자 퇴장 시 DB에 즉시 영속화
- AC-031: 네트워크 끊김 시 1s→2s→4s→...→30s 백오프 재연결
- AC-034: 편집 중 필드는 원격 변경 보류, 완료 후 LWW 적용
- AC-044: 팀 공유 회의록에만 "공동 편집" 버튼, 클릭 시 WS 연결
- AC-045: 비공유 회의록은 기존 로컬 편집 동작 유지
- AC-P01: 편집 전파 지연 < 1초 (P95)

## 수정 파일

| 파일 | 변경 |
|------|------|
| `backend/app/api/v1/collaboration/collab.py` | 신규: WS 엔드포인트 + ConnectionManager |
| `backend/services/collab_service.py` | 신규: LWW, room 관리 |
| `backend/schemas/collab.py` | 신규: 메시지 스키마 |
| `backend/app/api/v1/minutes/minutes.py` | 추가: PATCH /minutes/{task_id} |
| `client/lib/services/collab_socket_service.dart` | 신규: WS 클라이언트 |
| `client/lib/providers/collab_minutes_provider.dart` | 신규: AsyncNotifier + 상태 |
| `client/lib/widgets/collab_presence_bar.dart` | 신규: Presence 표시 |
| `client/lib/widgets/collab_editing_indicator.dart` | 신규: 편집 중 표시 |
| `client/lib/screens/result_screen.dart` | 수정: _MinutesTab 확장 |
| `client/pubspec.yaml` | 추가: web_socket_channel ^3.0.0 |

## 제외 항목

- 버전 히스토리/복구 (후속 SPEC)
- CRDT (Yjs/Automerge)
- 댓글/코멘트
- 오프라인 편집
- 커서 위치 동기화 (대신 "편집 중인 필드"로 대체)
- 섹션/행 추가/삭제
