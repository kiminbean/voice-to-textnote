# SPEC-COLLAB-001 Acceptance Criteria

## 검증 방법
본 문서는 spec.md의 REQ-COLLAB-001-* 요구사항이 코드와 테스트로 충족되었는지 추적한다.

## Acceptance Criteria

### REQ-COLLAB-001-001: WebSocket 실시간 통신 채널
- 상태: MET
- 증거: backend/app/api/v1/collaboration/collab.py — `WS /api/v1/collab/{task_id}/ws` 엔드포인트, JWT 쿼리 파라미터 인증, 연결 시 문서 스냅샷 전송, 연결 해제 시 Presence 제거, 잘못된 토큰 시 close 4401

### REQ-COLLAB-001-002: Per-field LWW 충돌 해결
- 상태: MET
- 증거: backend/services/collab_service.py — 서버 타임스탬프 부여, 필드별 최종 수정 시각 추적, LWW (later timestamp wins), 셀 단위 독립 편집, JSON 문서 구조 관리

### REQ-COLLAB-001-003: Room 관리 및 Presence
- 상태: MET
- 증거: backend/services/collab_service.py — task_id별 Room 관리 (최대 5명), 입장/퇴장 시 Presence 브로드캐스트, 6번째 사용자 거부 (close 4403)

### REQ-COLLAB-001-004: Debounced 영속화
- 상태: MET
- 증거: backend/services/collab_service.py — Redis `collab:doc:{task_id}` 즉시 갱신, 3초 debounce 후 DB 저장, 마지막 사용자 퇴장 시 즉시 DB flush

### REQ-COLLAB-001-005: Flutter 클라이언트
- 상태: MET
- 증거: client/lib/services/collab_service.dart (web_socket_channel), client/lib/providers/collab_provider.dart (AsyncNotifier, 자동 재연결), client/lib/widgets/presence_overlay.dart (활성 사용자 아바타)
