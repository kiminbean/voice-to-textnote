## SPEC-SEC-002 Progress

- Started: 2026-06-14
- Mode: sub-agent (team tools unavailable, graceful fallback)
- Development: TDD (Red-Green-Refactor)
- Branch: feature/SPEC-SEC-002
- Status: **COMPLETED**
- Completed: 2026-06-14
- PR: #28
- Issue: #27

### Quality Gates

- Backend: 3246 passed, 2 pre-existing env failures
- Flutter: 301 passed
- ruff check: All passed
- dart analyze: No issues found
- 2026-06-14 Android release/profile cleartext split:
  - `cd client && flutter test test/config/network_security_config_test.dart` -> `4 passed`
  - `cd client && flutter build apk --release` -> `✓ Built build/app/outputs/flutter-apk/app-release.apk`
  - `cd client && flutter build apk --debug` -> `✓ Built build/app/outputs/flutter-apk/app-debug.apk`
  - `python3 client/scripts/verify_release_readiness.py` -> `0 errors, 2 warnings`
  - `python3 client/scripts/verify_release_readiness.py --strict` -> expected failure without Firebase/APNs/App Store Connect secrets, physical device IDs, and release E2E evidence JSON
- 2026-06-15 Android emulator runtime gate:
  - Android emulator `36.6.11` + `system-images;android-36;google_apis;arm64-v8a` installed; AVD `voice_to_textnote_api36` booted with `sys.boot_completed=1`
  - `cd client/android && ./gradlew :app:connectedDebugAndroidTest --no-daemon` -> `Finished 1 tests on voice_to_textnote_api36(AVD) - 16`, `BUILD SUCCESSFUL`
  - `cd client && flutter test test/config/network_security_config_test.dart` -> `4 passed`
  - `cd client && flutter build apk --release` -> `✓ Built build/app/outputs/flutter-apk/app-release.apk`
  - `aapt2 dump xmltree --file res/8G.xml client/build/app/outputs/flutter-apk/app-release.apk` -> `base-config cleartextTrafficPermitted=false`

### AC Coverage

- AC-001: Info.plist NSAllowsArbitraryLoads=false + NSExceptionDomains — PASS
- AC-002: Android `src/main` Release/Profile cleartext 전면 차단 + `src/debug` localhost/Tailscale 전용 예외 — PASS
- AC-M02 emulator proxy: Debug 앱 런타임 `NetworkSecurityPolicy`가 localhost/Tailscale cleartext만 허용 — PASS on `voice_to_textnote_api36`
- AC-M03 artifact proxy: Release APK 내부 network security XML이 cleartext 전면 차단 — PASS; 실제 HTTP 실패 UX는 실기기 수동 확인 유지
- AC-003: 매직 바이트 불일치 시 422 반환 (file_signature.py + validators.py) — PASS
- AC-004: 프로덕션 환경 HSTS 헤더 (settings.environment 기반) — PASS
- AC-005: 클라이언트 매직 바이트 + 확장자 + 크기 사전 검증 — PASS
