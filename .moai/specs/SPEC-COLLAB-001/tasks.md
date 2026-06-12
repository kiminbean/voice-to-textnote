## Task Decomposition
SPEC: SPEC-COLLAB-001

| Task ID | Description | Requirement | Dependencies | Planned Files | Status |
|---------|-------------|-------------|--------------|---------------|--------|
| T-001 | CollabMessage Pydantic 스키마 정의 | REQ-COLLAB-010,013 | - | backend/schemas/collab.py | pending |
| T-002 | CollabConnectionManager 클래스 구현 | REQ-COLLAB-001,002,003,004 | - | backend/app/api/v1/collaboration/collab.py | pending |
| T-003 | WebSocket 엔드포인트 + JWT 인증 | REQ-COLLAB-001,050 | T-001, T-002 | backend/app/api/v1/collaboration/collab.py | pending |
| T-004 | collab 라우터 등록 | REQ-COLLAB-001 | T-003 | backend/app/api/v1/collaboration/__init__.py | pending |
| T-005 | M1 단위 테스트 (Connection, JWT, Room) | AC-001~005 | T-003 | backend/tests/unit/test_collab_connection.py | pending |
| T-006 | CollabService LWW + Redis 상태 관리 | REQ-COLLAB-010,011,012 | T-001 | backend/services/collab_service.py | pending |
| T-007 | 디바운스 DB 영속화 | REQ-COLLAB-020,021,022 | T-006 | backend/services/collab_service.py | pending |
| T-008 | PATCH /minutes/{task_id} 엔드포인트 | REQ-COLLAB-020 | T-007 | backend/app/api/v1/minutes/minutes.py | pending |
| T-009 | M2 통합 테스트 (LWW, 영속화) | AC-010~023 | T-007, T-008 | backend/tests/integration/test_collab_service.py | pending |
| T-010 | CollabSocketService (web_socket_channel) | REQ-COLLAB-030 | T-003 | client/lib/services/collab_socket_service.dart | pending |
| T-011 | CollabMinutesNotifier (Riverpod) | REQ-COLLAB-031,032,033 | T-010 | client/lib/providers/collab_minutes_provider.dart | pending |
| T-012 | pubspec.yaml web_socket_channel 추가 | REQ-COLLAB-030 | - | client/pubspec.yaml | pending |
| T-013 | M3 단위 테스트 | AC-030~034 | T-011 | client/test/providers/collab_minutes_provider_test.dart | pending |
| T-014 | CollabPresenceBar 위젯 | REQ-COLLAB-042 | T-011 | client/lib/widgets/collab_presence_bar.dart | pending |
| T-015 | CollabEditingIndicator 위젯 | REQ-COLLAB-041,043 | T-011 | client/lib/widgets/collab_editing_indicator.dart | pending |
| T-016 | _MinutesTab 협업 통합 | REQ-COLLAB-040,044,045 | T-014, T-015 | client/lib/screens/result_screen.dart | pending |
| T-017 | M4 위젯 테스트 | AC-040~045 | T-016 | client/test/widgets/collab_presence_bar_test.dart | pending |
| T-018 | 보안 강화 (Role gating, Rate limit) | REQ-COLLAB-050,051,052,053 | T-003 | backend/app/api/v1/collaboration/collab.py | pending |
| T-019 | M5 보안 테스트 | AC-050~053 | T-018 | backend/tests/unit/test_collab_security.py | pending |
| T-020 | M6 통합/E2E 테스트 | AC-P01~P03, AC-E01~E03 | T-009, T-019 | backend/tests/e2e/test_collab_e2e.py | pending |
