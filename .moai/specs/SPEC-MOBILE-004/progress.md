## SPEC-MOBILE-004 Progress

- Started: 2026-06-13
- Completed: 2026-06-13
- Mode: TDD (Red-Green-Refactor)
- Team mode: Not available (sub-agent parallel delegation)

### Batch 1 — 백엔드 FCM/Celery (commit 658e445)
- [x] T-001: permission_dialog.dart recursion fix
- [x] T-002/T-003/T-004: Client FCM init, DeviceApi, background handler
- [x] T-006: push_service.py — firebase_admin + MOCK fallback
- [x] T-007: config.py — firebase_credentials_path
- [x] T-008: celery_push_hooks.py — fire_push_sync wiring
- Backend regression: 135 passed, 0 failed; Flutter: 23 passed

### Batch 2 — 클라이언트 녹음/권한 (commit 41679ad)
- [x] T-005: main.dart WidgetsBindingObserver + DeepLinkService
- [x] T-009: RecordingRecoveryService (SharedPreferences) + 6 tests
- [x] T-010: RecordingRecoveryDialog (미완료 녹음 감지)
- [x] T-011: Android flushRecording 실제 구현 (알림 갱신)
- [x] T-012: RecordingProvider/BGMService pause/resume
- [x] T-013: PermissionService 저장공간 권한
- [x] T-015: permissionRecheckProvider + lifecycle resume
- [~] T-014: rationale-before-request (P2, cancelled)
- Flutter: exit code 0 (전체 통과)

### Batch 3 — 문서/배포 (commit 9e73945)
- [x] T-016: app-store-metadata.md (기존 240라인 유지)
- [x] T-017: screenshot-guide.md
- [x] T-018: ats-proguard-config.md
- [x] T-019: firebase-setup-guide.md
- [x] T-020: e2e-device-checklist.md (25항목)
- [x] T-021: DB 마이그레이션 검증 (4 passed)

### 최종 검증
- Flutter: exit code 0 (전체 통과)
- Backend (SPEC-MOBILE-004): 17 passed, 0 failed
- analyze lib/ test/: 0 errors
- 2026-06-15 PR 32 post-fix cross-check: GitHub Actions `Test & Lint`, `Flutter Analyze, Test, Android Build`, `Flutter iOS No-Codesign Build` 모두 `pass`; strict physical-device gate는 hosted runner에서 `skipping`으로 남음.
