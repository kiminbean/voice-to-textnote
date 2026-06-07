# SPEC-MOBILE-001 Compact (v2.0.0)

> Run phase용 축약본. 전체 문서: spec.md

---

## Requirements (EARS)

### REQ-MOBILE-001: 빌드 설정 [EXISTING] — 작업 불필요
- 001-01~06: 아이콘, 스플래시, 번들ID, Android 플랫폼, SDK 버전 — 모두 구현 완료

### REQ-MOBILE-002: Push 알림 — Firebase Admin SDK + DB Persistence [MODIFY]

| ID | 요구사항 | 상태 | 우선순위 |
|----|---------|------|---------|
| 002-01 | Firebase Console 프로젝트 생성, iOS/Android 앱 등록 | [NEW][EXTERNAL] | P1 |
| 002-02 | firebase_messaging FCM 토큰 수신 | [EXISTING] | P1 |
| 002-03 | 디바이스 등록 정보 PostgreSQL `device_tokens` 테이블에 영속 저장 | [MODIFY] | P1 |
| 002-04 | Firebase Admin SDK (`firebase-admin`) 실제 FCM 전송 (mock 제거) | [MODIFY] | P1 |
| 002-05 | Celery `on_success`/`on_failure` hook에서 Push Service 호출 | [MODIFY] | P1 |
| 002-06 | FCM 토큰 무효화 시 DB에서 자동 제거 | [NEW] | P1 |
| 002-07 | Push payload에 `meeting_id` 포함 | [NEW] | P2 |
| 002-08 | flutter_local_notifications 포그라운드 알림 | [EXISTING] | P2 |
| 002-09 | Push 탭 시 딥링크 네비게이션 | [NEW] → REQ-006 | P2 |

### REQ-MOBILE-003: 백그라운드 오디오 녹음 [MODIFY — 검증 필요]

| ID | 요구사항 | 상태 |
|----|---------|------|
| 003-01 | iOS UIBackgroundModes: audio | [EXISTING] |
| 003-02 | Android Foreground Service (MICROPHONE) | [MODIFY — 실기기 검증] |
| 003-03 | 백그라운드 녹음 인디케이터 | [MODIFY — 실기기 검증] |
| 003-04 | audio_session 패키지 통합 | [EXISTING] |
| 003-05 | 앱 종료 시 녹음 파일 보존 (flush ≤10초 간격) | [MODIFY — 실기기 검증] |

### REQ-MOBILE-004: 권한 관리 [EXISTING] — 작업 불필요
- 004-01~05: 마이크, 알림, 설정 이동 — 모두 구현 완료

### REQ-MOBILE-005: 앱 스토어 배포 준비 [NEW]

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 005-01 | App Store Connect 앱 정보 등록 | P2 |
| 005-02 | Google Play Console 앱 정보 등록 | P2 |
| 005-03 | iOS/Android 스크린샷 준비 | P2 |
| 005-04 | 개인정보 처리방침 URL 설정 | P2 |
| 005-05 | ATS 예외 사유 문서화 (Tailscale HTTP) | P2 |

### REQ-MOBILE-006: 딥링크 + 앱 내 네비게이션 [NEW]

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 006-01 | iOS Info.plist `CFBundleURLSchemes`에 `voicetextnote` 등록 | P1 |
| 006-02 | Android AndroidManifest.xml `<intent-filter>` 딥링크 등록 | P1 |
| 006-03 | go_router 딥링크 라우트 (`voicetextnote://summary/{meetingId}`) | P1 |
| 006-04 | Push 알림 탭 → `meeting_id` 추출 → go_router 네비게이션 | P1 |
| 006-05 | Cold start: `getInitialMessage()` → 초기 라우트 설정 | P2 |

---

## Acceptance Criteria (Given/When/Then)

### AC-002-PROD: Push 알림 프로덕션 [NEW]
**Given** 사용자가 오디오를 업로드하고 FCM 토큰이 등록되어 있을 때
**When** Celery 파이프라인이 완료되면
**Then** Firebase Admin SDK를 통해 실제 Push 알림이 전송되고, payload에 `meeting_id`가 포함된다

### AC-006-DEEP: 딥링크 네비게이션 [NEW]
**Given** 사용자가 Push 알림을 수신했을 때
**When** 알림을 탭하면
**Then** 앱이 실행되고 `/summary/{meetingId}` 화면으로 직접 이동한다 (hot/cold state 모두)

### AC-007-PERSIST: 디바이스 등록 영속화 [NEW]
**Given** 사용자 디바이스가 FCM 토큰을 등록했을 때
**When** 백엔드 서버를 재시작하면
**Then** PostgreSQL에서 디바이스 정보가 복원되어 Push 알림이 정상 동작한다

### AC-001 ~ AC-006 (기존): 아이콘/스플래시, Android 빌드, 백그라운드 녹음, 권한 UX, FCM 토큰 등록 — 모두 [EXISTING]

---

## Files to Modify

### New Files
| File | Purpose |
|------|---------|
| `backend/models/device.py` | Device SQLAlchemy model |
| `backend/alembic/versions/xxx_add_device_tokens.py` | DB migration |

### Modified Files
| File | Change |
|------|--------|
| `backend/services/push_service.py` | in-memory → DB + mock → real Firebase SDK |
| `backend/app/api/v1/auth/devices.py` | DB-based device management |
| `backend/core/config.py` | FIREBASE_SERVICE_ACCOUNT_PATH setting |
| `backend/workers/tasks/` | Pipeline completion push trigger |
| `client/ios/Runner/Info.plist` | remote-notification + URL scheme |
| `client/ios/Runner/Entitlements` | aps-environment |
| `client/android/.../AndroidManifest.xml` | Deep link intent-filter |
| `client/lib/router/` | go_router deep link route |
| `client/lib/main.dart` | Initial message handling |
| `backend/requirements.txt` | `firebase-admin` dependency |

---

## Exclusions (What NOT to Build)

1. Apple Watch / WearOS 연동
2. iOS Widget / Android Widget
3. Siri / Google Assistant 통합
4. 오프라인 STT 처리
5. TestFlight / Internal Testing 자동화
6. 다국어(i18n) 지원

---

*SPEC-MOBILE-001 v2.0.0 compact — generated 2026-06-06*
