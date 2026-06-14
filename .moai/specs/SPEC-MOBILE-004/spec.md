---
id: SPEC-MOBILE-004
version: "1.0.5"
status: completed
created: "2026-06-13"
updated: "2026-06-15"
author: sisyphus
priority: high
issue_number: 24
depends_on: SPEC-MOBILE-001
---

# SPEC-MOBILE-004: 모바일 프로덕션 완성

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 초안 작성 — SPEC-MOBILE-001 Phase D/E 완성 + 심층 코드 분석 기반 결함 수정 | sisyphus |
| 1.0.1 | 2026-06-15 | strict release readiness를 self-hosted GitHub Actions `workflow_dispatch` 게이트로 승격 | Codex |
| 1.0.2 | 2026-06-15 | GitHub mobile release environment preflight 추가 | Codex |
| 1.0.3 | 2026-06-15 | GitHub mobile release environment 구성 스크립트 추가 | Codex |
| 1.0.4 | 2026-06-15 | self-hosted macOS runner 후보 장비 preflight 추가 | Codex |
| 1.0.5 | 2026-06-15 | Release E2E evidence scaffold 생성 스크립트 추가 | Codex |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter 3.24+ / Dart 3.5+ |
| 상태관리 | Riverpod 2.6+ (flutter_riverpod) |
| Push 알림 | firebase_messaging ^15.1.0 + flutter_local_notifications ^18.0.0 |
| 백엔드 Push | Firebase Admin SDK (firebase-admin >= 6.0, Python) |
| 권한 관리 | permission_handler ^11.3.0 |
| 오디오 녹음 | record ^6.0.0 + audio_session ^0.1.21 |
| 로컬 저장소 | shared_preferences ^2.3+ (녹음 경로 복원용) |
| 라우팅 | go_router 15.1+ |
| 백엔드 | FastAPI + Celery + PostgreSQL + Redis |
| 대상 플랫폼 | iOS 15+, Android 10+ (API 29+), macOS 13+ |
| 개발 환경 | macOS (M4 Mac mini), Xcode 15+, Android Studio |
| 개발 방법론 | TDD (Red-Green-Refactor) |
| 선행 SPEC | SPEC-MOBILE-001 (completed, v2.0.0 Phase A/B/C) |

---

## 2. 가정 (Assumptions)

- SPEC-MOBILE-001 v2.0.0의 Phase A/B/C 코드가 구현 완료된 상태이다 (device_tokens DB, PushService skeleton, 딥링크 서비스, 권한 서비스).
- Firebase 프로젝트는 아직 생성되지 않았으며, 코드 수준 wiring은 완료하고 실제 Firebase 연동은 문서화로 제공한다.
- Apple Developer 계정이 사용 가능하다 (Push 알림 인증서, App Store 배포용).
- `firebase-admin>=6.0` Python 패키지가 이미 pyproject.toml에 선언되어 있다.
- `firebase_messaging` / `flutter_local_notifications` Flutter 패키지가 pubspec.yaml에 선언되어 있다.
- 기존 3621개 백엔드 테스트와 55개 Flutter 테스트가 통과하는 상태를 유지해야 한다.

---

## 3. 요구사항 (Requirements)

### REQ-MOBILE-004-001: Push 알림 런타임 연동 [P0-CRITICAL]

**EARS 형식**: 회의록 처리 파이프라인이 완료되었을 때, 시스템은 Firebase Admin SDK를 통해 FCM Push 알림을 실제로 전송하고, 클라이언트는 이를 수신하여 해당 회의록 화면으로 딥링크 네비게이션해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-004-001-01 | `main.dart`에서 앱 시작 시 `NotificationNotifier.initialize()`를 호출하여 FCM을 초기화한다 | P0 | [NEW] |
| REQ-MOBILE-004-001-02 | FCM 토큰 획득 후 `POST /api/v1/devices/register`로 백엔드에 등록한다 (api_client 통합) | P0 | [NEW] |
| REQ-MOBILE-004-001-03 | `registerFCMBackgroundHandler()`를 호출하여 백그라운드 메시지 핸들러를 등록한다 | P0 | [NEW] |
| REQ-MOBILE-004-001-04 | `DeepLinkService.handleBackgroundResume()`과 `handleUrlScheme()`을 main.dart/app_router에 연동한다 | P1 | [NEW] |
| REQ-MOBILE-004-001-05 | 백엔드 `push_service.py`에서 MOCK 코드를 제거하고 실제 Firebase Admin SDK FCM 전송을 활성화한다 | P0 | [NEW] |
| REQ-MOBILE-004-001-06 | `backend/app/config.py`에 `FIREBASE_CREDENTIALS_PATH` 설정 필드를 추가한다 | P0 | [NEW] |
| REQ-MOBILE-004-001-07 | Celery 파이프라인 태스크 완료/실패 지점에 `on_pipeline_success/on_failure` hook을 연동한다 | P0 | [NEW] |
| REQ-MOBILE-004-001-08 | `flutter_local_notifications` Android 알림 채널을 생성한다 (Push 알림 표시용, `recording_channel`과 별개) | P1 | [NEW] |

**검증 참고**: Firebase 프로젝트 미생성 상태에서는 FCM 전송이 실패하므로, 코드 wiring 완료 후 Firebase 설정(E2E) 단계에서 실제 Push 전송을 검증한다. wiring 자체는 단위 테스트로 검증한다 (initialize 호출 여부, hook 호출 여부, config 필드 존재 여부).

---

### REQ-MOBILE-004-002: 백그라운드 녹음 복원력 강화 [P1]

**EARS 형식**: 사용자가 백그라운드 녹음 중 앱이 시스템에 의해 종료되었을 때, 시스템은 녹음 파일 경로를 영속 저장소에서 복원하고 녹음 데이터를 손실 없이 보존해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-004-002-01 | 녹음 시작 시 파일 경로를 `SharedPreferences`에 저장하고, 녹음 중 10초 간격으로 진행 상태를 업데이트한다 | P1 | [NEW] |
| REQ-MOBILE-004-002-02 | 앱 재시작 시 미완료 녹음을 감지하고 사용자에게 복원 또는 삭제 옵션을 제공한다 | P1 | [NEW] |
| REQ-MOBILE-004-002-03 | `RecordingProvider`에 `pauseRecording()` / `resumeRecording()` 메서드를 구현한다 | P2 | [NEW] |
| REQ-MOBILE-004-002-04 | Android `RecordingService.flushRecording` MethodChannel 핸들러에 실제 파일 flush 로직을 구현한다 | P1 | [NEW] |
| REQ-MOBILE-004-002-05 | 백그라운드 녹음 완료 시 자동 업로드를 트리거한다 (Foreground Service 확장 또는 workmanager) | P2 | [NEW] |

**검증 참고**: REQ-002-01의 SharedPreferences 저장은 단위 테스트로 검증 가능. REQ-002-02의 복원 로직은 통합 테스트로 시뮬레이션. 실제 강제 종료 시나리오는 실기기 테스트가 필요.

---

### REQ-MOBILE-004-003: 권한 관리 통합 및 버그 수정 [P0]

**EARS 형식**: 앱이 실행될 때, 시스템은 모든 필요한 플랫폼 권한(마이크, 알림, 저장공간)을 통합적으로 관리하고, 권한 거부 시 무한 루프나 크래시 없이 안전하게 사용자에게 안내해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-004-003-01 | `permission_dialog.dart:145-168`의 `openAppSettings()` 무한 재귀 버그를 수정한다 — 로컬 함수가 `PermissionService.openAppSettings`를 가리지 않도록 분리 | P0 | [NEW] |
| REQ-MOBILE-004-003-02 | `PermissionService`에 저장공간/미디어 접근 권한을 추가한다 (`Permission.storage`, `Permission.audio` for Android 13+) | P1 | [NEW] |
| REQ-MOBILE-004-003-03 | Android에서 권한 요청 전 `shouldShowRationale` 확인 후 rationale 다이얼로그를 표시하는 플로우를 추가한다 | P2 | [NEW] |
| REQ-MOBILE-004-003-04 | 설정 앱에서 돌아온 후(`WidgetsBindingObserver.didChangeAppLifecycleState`) 권한 상태를 재확인하는 로직을 추가한다 | P1 | [NEW] |
| REQ-MOBILE-004-003-05 | iOS/Android 네이티브 메모리/저장공간 확인 Platform Channel을 구현한다 (현재 Dart fallback을 대체) | P2 | [NEW] |

**검증 참고**: REQ-003-01의 무한 재귀 버그는 회귀 테스트로 즉시 검증 가능 (openAppSettings 호출 시 스택 오버플로우가 발생하지 않는지 확인).

---

### REQ-MOBILE-004-004: App Store 배포 준비 (Phase D) [P2]

**EARS 형식**: 앱이 앱 스토어에 제출될 때, 시스템은 App Store / Google Play 가이드라인에 부합하는 메타데이터, 스크린샷, 개인정보 처리방침을 포함해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-004-004-01 | App Store Connect 앱 정보(이름, 설명, 카테고리, 키워드) 메타데이터를 작성한다 | P2 | [NEW] |
| REQ-MOBILE-004-004-02 | Google Play Console 앱 정보 메타데이터를 작성한다 | P2 | [NEW] |
| REQ-MOBILE-004-004-03 | 디바이스별 스크린샷 촬영 가이드를 작성한다 (iPhone 6.7", 5.5", iPad 12.9", Android phone/tablet) | P2 | [NEW] |
| REQ-MOBILE-004-004-04 | 개인정보 처리방침(Privacy Policy) 페이지 또는 URL을 설정한다 | P2 | [NEW] |
| REQ-MOBILE-004-004-05 | iOS ATS(App Transport Security) 예외 사유를 문서화한다 (Tailscale HTTP 접속) | P2 | [NEW] |
| REQ-MOBILE-004-004-06 | Android ProGuard/R8 난독화 규칙을 설정한다 (whisper_ggml_plus, firebase 네이티브 라이브러리 보호) | P2 | [NEW] |

---

### REQ-MOBILE-004-005: Firebase E2E 통합 검증 (Phase E) [P1]

**EARS 형식**: Firebase 프로젝트가 설정되었을 때, 시스템은 Push 알림의 end-to-end 흐름을 실기기에서 검증하고, device_tokens DB 마이그레이션을 실행 검증해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-004-005-01 | Firebase Console 프로젝트 생성 및 iOS/Android 앱 등록 절차를 단계별로 문서화한다 | P1 | [NEW] |
| REQ-MOBILE-004-005-02 | 서비스 계정 키 발급 및 백엔드 환경변수(`FIREBASE_CREDENTIALS_PATH`) 등록 절차를 문서화한다 | P1 | [NEW] |
| REQ-MOBILE-004-005-03 | APNs 인증서(.p8) 발급 및 Firebase 연동 절차를 문서화한다 | P1 | [NEW] |
| REQ-MOBILE-004-005-04 | `GoogleService-Info.plist` (iOS) 및 `google-services.json` (Android) 설정 가이드를 작성한다 | P1 | [NEW] |
| REQ-MOBILE-004-005-05 | 실기기 E2E 테스트 체크리스트를 작성한다 (녹음 → 업로드 → Push 수신 → 딥링크 네비게이션) | P1 | [NEW] |
| REQ-MOBILE-004-005-06 | `device_tokens` DB 마이그레이션 실행 검증 (`alembic upgrade head`) | P1 | [NEW] |

---

## 4. MVP 범위에서 제외

| 기능 | 제외 사유 | 향후 SPEC |
|------|----------|----------|
| Siri / Google Assistant 음성 명령 통합 | 핵심 기능 아님, 사용자 수요 미확인 | SPEC-MOBILE-005 |
| iOS Widget / Android Widget | UX 개선 단계, 별도 디자인 필요 | SPEC-MOBILE-006 |
| Apple Watch / WearOS 연동 | 핵심 기능 아님, 사용자 수요 미확인 | SPEC-MOBILE-007 |
| 다국어(i18n) 지원 | 별도 SPEC으로 분리 | SPEC-I18N-001 |
| 클라우드 동기화 | 로컬 전용 원칙과 충돌 검토 필요 | 별도 검토 |

---

## 5. 기술 설계

### 5.1 Push 알림 연동 아키텍처

```
[현재 - 스캐폴드만 존재, 연동 안 됨]
  Client: NotificationNotifier.initialize() → 데드 코드
  Backend: PushService.send_push() → MOCK 로그만

[목표 - 런타임 완전 연동]
  1. main.dart → NotificationNotifier.initialize() 호출
  2. FCM 토큰 획득 → api_client → POST /api/v1/devices/register
  3. registerFCMBackgroundHandler() → 백그라운드 isolate 핸들러 등록
  4. Celery task 완료 → on_pipeline_success hook → PushService.send_to_user()
  5. PushService → Firebase Admin SDK → FCM HTTP v1 API → 디바이스 Push
  6. 디바이스 수신 → flutter_local_notifications 표시 → 딥링크 → /summary/{meetingId}
```

### 5.2 백그라운드 녹음 복원 메커니즘

```
녹음 시작:
  RecordingProvider.startRecording()
    → BackgroundRecordingService.startRecording()
    → SharedPreferences.setString('recording_path', path)
    → SharedPreferences.setString('recording_started_at', timestamp)

녹음 중 (10초 간격):
  _flushTimer → SharedPreferences.setInt('recording_elapsed', seconds)

앱 재시작:
  RecordingProvider 초기화 시
    → SharedPreferences.getString('recording_path')
    → 경로 존재 + 파일 유효 → 복원 다이얼로그 표시
    → "이전 녹음이 있습니다. 계속하시겠습니까?" [복원] [삭제]
```

### 5.3 권한 관리 통합 구조

```
PermissionService (통합 관리자)
  ├── requestMicrophonePermission()
  ├── requestNotificationPermission()
  ├── requestStoragePermission()       // [NEW] Android 13+ 미디어 접근
  ├── checkAllPermissions() → PermissionStatus Map
  ├── shouldShowRationale(permission) → bool
  └── openAppSettings()                // 버그 수정: 로컬 함수 가림 방지

PermissionDialog (위젯)
  ├── 권한별 rationale 표시
  ├── 요청 → 결과 처리
  ├── permanentlyDenied → 설정 이동 (안전한 openAppSettings 호출)
  └── 설정 복귀 후 didChangeAppLifecycleState → 권한 재확인
```

### 5.4 디렉토리 구조 변경

```
client/
├── lib/
│   ├── main.dart                            # [MODIFY] NotificationNotifier.initialize() 호출 추가
│   ├── services/
│   │   ├── push_notification_service.dart   # [MODIFY] registerFCMBackgroundHandler 활성화
│   │   ├── permission_service.dart          # [MODIFY] 저장공간 권한 추가
│   │   ├── background_recording_service.dart # [MODIFY] SharedPreferences 경로 저장
│   │   └── api_client.dart                  # [MODIFY] FCM 토큰 등록 엔드포인트 통합
│   ├── providers/
│   │   ├── notification_provider.dart       # [VERIFY] initialize()가 호출되는지
│   │   └── recording_provider.dart          # [MODIFY] pause/resume, 복원 로직
│   ├── widgets/
│   │   └── permission_dialog.dart           # [FIX] openAppSettings 무한 재귀 수정
│   └── router/
│       └── app_router.dart                  # [MODIFY] DeepLinkService 핸들러 연동
├── android/
│   └── app/src/main/kotlin/.../
│       ├── MainActivity.kt                  # [MODIFY] flushRecording 실제 구현
│       └── RecordingService.kt              # [VERIFY] Foreground Service 안정성
└── ios/
    └── Runner/Info.plist                    # [VERIFY] 백그라운드 모드 설정

backend/
├── app/
│   ├── config.py                            # [MODIFY] FIREBASE_CREDENTIALS_PATH 추가
│   └── workers/
│       ├── hooks/
│       │   └── celery_push_hooks.py         # [VERIFY] hook 시그니처
│       └── tasks/
│           └── (pipeline tasks)             # [MODIFY] 완료/실패 시 hook 호출 추가
└── services/
    └── push_service.py                      # [MODIFY] MOCK → 실제 FCM 전송 활성화

docs/
├── firebase-setup-guide.md                  # [NEW] Firebase 설정 절차
├── app-store-metadata.md                    # [NEW] App Store 메타데이터
├── google-play-metadata.md                  # [NEW] Google Play 메타데이터
└── mobile-e2e-checklist.md                  # [NEW] 실기기 E2E 테스트 체크리스트
```

---

## 6. 의존성 (Dependencies)

### 선행 SPEC

| SPEC | 상태 | 관계 |
|------|------|------|
| SPEC-MOBILE-001 | completed (v2.0.0) | Phase A/B/C 인프라 스캐폴드 제공 |
| SPEC-MOBILE-002 | implementation-complete | 오프라인 STT (독립적) |
| SPEC-MOBILE-003 | partial | 오프라인 STT 하드닝 (독립적) |
| SPEC-SSE-001 | completed | SSE 실시간 (Push와 보완적) |

### 추가 클라이언트 의존성 (검토 필요)

```yaml
# pubspec.yaml — workmanager는 P2에서만 필요, 의존성 추가 여부 검토
# workmanager: ^0.5.2  # 백그라운드 업로드 (REQ-002-05, Foreground Service 대안 검토 후 결정)
```

### 기존 의존성 (변경 없음, 활성화만)

```yaml
# 이미 pubspec.yaml에 선언됨
dependencies:
  firebase_core: ^3.8.0
  firebase_messaging: ^15.1.0
  flutter_local_notifications: ^18.0.0
  permission_handler: ^11.3.0
  audio_session: ^0.1.21
  shared_preferences: ^2.3+  # 경로 복원용
```

```
# 백엔드 — 이미 pyproject.toml에 선언됨
firebase-admin>=6.0
```

### 외부 서비스

| 서비스 | 용도 | 설정 필요 |
|--------|------|----------|
| Firebase Console | FCM 프로젝트, iOS/Android 앱 등록 | GoogleService-Info.plist, google-services.json (REQ-005) |
| Firebase Admin SDK | 서비스 계정 키 (서버 FCM 전송) | serviceAccountKey.json → `FIREBASE_CREDENTIALS_PATH` (REQ-005) |
| Apple Developer | APNs 인증서 (.p8 키) | Firebase에 업로드 (REQ-005) |
| Google Play Console | Android 앱 등록 | 서명 키 (REQ-004) |

---

## 7. 구현 현황

**버전**: v1.0.0
**진행 상태**: completed (구현 및 검증 완료)

### 심층 코드 분석 기반 발견사항

**P0-CRITICAL (즉시 수정 필요)**:
1. `NotificationNotifier.initialize()` 데드 코드 — 어디에서도 호출되지 않음
2. `fcmTokenProvider` 소비자 0건 — FCM 토큰이 백엔드로 전송되지 않음
3. `registerFCMBackgroundHandler()` 호출 누락 — 백그라운드 Push 미처리
4. 백엔드 `PushService` MOCK 모드 — 실제 FCM 전송 안 됨
5. Celery push hooks 데드 코드 — 파이프라인에서 호출 안 됨
6. `permission_dialog.dart` 무한 재귀 버그 — `openAppSettings()` 스택 오버플로우

**P1 (강화 필요)**:
7. 백그라운드 녹음 crash recovery 부재
8. Android `flushRecording` no-op
9. `DeepLinkService` 핸들러 미연동
10. `PermissionService` 저장공간 권한 누락

**P2 (준비 사항)**:
11. App Store / Google Play 메타데이터
12. Privacy Policy, ATS 문서화
13. Android ProGuard 규칙

---

## 8. 기술 제약사항

| 제약 | 설명 |
|------|------|
| Firebase 프로젝트 미생성 | Push 알림 E2E 테스트 불가, 코드 wiring만 완료 |
| Apple Developer 계정 | App Store 배포 불가, 메타데이터 준비만 |
| iOS 실기기 필요 | Push/백그라운드 녹음은 시뮬레이터로 완전 검증 불가 |
| 기존 파이프라인 영향 | Celery hook 연동 시 회귀 테스트 필수 |

### 2026-06-14 재검증

- Backend Firebase/Push wiring 포함 전체 회귀: `venv/bin/python -m pytest backend -q` -> `3323 passed, 16 skipped`, coverage `98.62%`
- Device token registration/unregistration focused gate: `venv/bin/python -m pytest -o addopts="" backend/tests/unit/test_devices_api_coverage.py backend/tests/test_push_service_db.py backend/tests/test_device_token_migration.py -q` -> `25 passed`; `device_tokens.device_id`와 `(user_id, device_id)` unregister로 요청한 기기만 비활성화.
- Flutter notification/device client tests 포함 전체 회귀: `cd client && flutter test` -> `324 passed`
- Native build readiness: `cd client && ./scripts/verify_mobile.sh --native` -> Android APK와 iOS no-codesign Runner.app 빌드 성공
- Release readiness preflight: `python3 client/scripts/verify_release_readiness.py` -> `0 errors` (strict 외부 secret/device 검사는 별도 `--strict`; Android serial은 `adb devices -l`, iOS UDID는 `xcrun devicectl list devices`에서 실제 연결 상태까지 확인)
- 실제 Firebase Console 프로젝트, APNs key, Apple Developer provisioning, 실기기 Push 수신 E2E는 외부 계정/장비 의존으로 남음.

### 2026-06-15 App Store/Play 제출 자산 게이트 보강

- `client/scripts/verify_release_readiness.py` 기본 모드가 `docs/screenshot-guide.md`, `docs/privacy-policy.md`, App Store/Google Play 메타데이터, Privacy Policy URL, 스크린샷 시나리오, 1024x1024 무알파 앱 아이콘을 정적으로 검증한다.
- `docs/app-store-metadata.md`의 Privacy Policy URL은 제출 전 placeholder가 아닌 `https://voicetextnote.com/privacy`로 고정했다.
- `docs/screenshot-guide.md`는 iPhone 6.7"/6.5", iPad 12.9", Android phone/tablet 산출물 체크와 샘플 데이터 사용 원칙을 포함한다.
- 검증: `python3 -m py_compile client/scripts/verify_release_readiness.py && python3 client/scripts/verify_release_readiness.py` -> `release_readiness: 0 errors, 2 warnings`.
- strict 검증: `python3 client/scripts/verify_release_readiness.py --strict` -> release 문서 placeholder와 제출 자산 checks는 통과하고, Firebase/APNs/App Store Connect/실기기 입력 및 `RELEASE_E2E_EVIDENCE_PATH` 누락으로 예상 실패한다. 증거 파일은 `docs/release-e2e-evidence.example.json` 구조를 따라 Push/딥링크/백그라운드 녹음/HTTP 정책/PDF 공유 시나리오 pass 증거를 포함해야 한다.
- GitHub Actions strict gate: `.github/workflows/mobile.yml`의 `workflow_dispatch` `release-strict` job은 `self-hosted`, `macOS`, `mobile-release` runner에서 `client/scripts/verify_mobile.sh --native` 후 `python3 client/scripts/verify_release_readiness.py --strict`를 실행한다. 필요한 Firebase/APNs/App Store Connect secrets, Android/iOS device vars, `evidence_path` 입력은 `docs/e2e-device-checklist.md`에 문서화되어 있으며, regression test가 workflow snippet을 고정한다.
- GitHub release environment preflight: `python3 client/scripts/verify_github_mobile_release_env.py --repo kiminbean/voice-to-textnote`는 repository Environment, required secret/variable names, self-hosted runner labels를 확인한다. 현재 GitHub `mobile-release` Environment는 생성되어 통과하지만, self-hosted runner `0`개와 production secret/variable 미설정으로 strict CI 실행 전 외부 설정이 아직 필요하다.
- GitHub release environment configure: `python3 client/scripts/configure_github_mobile_release_env.py --repo kiminbean/voice-to-textnote`는 같은 이름의 로컬 환경변수에서 GitHub Environment secrets/vars를 등록한 뒤 verifier를 실행한다. secret 값이 없는 현재 세션에서는 dry-run/unit tests로 명령 surface만 검증했고, 실제 production secret 등록은 외부 보안 입력이 필요하다.
- Self-hosted runner 후보 장비 preflight: `ANDROID_DEVICE_SERIAL=<serial> IOS_DEVICE_UDID=<udid> python3 client/scripts/verify_mobile_release_runner.py`는 macOS, Flutter/Android SDK 36/Xcode/CocoaPods, Android `adb device`, iOS `devicectl available` 상태를 확인한다. 현재 로컬은 Flutter/Android/Xcode는 준비됐지만 Android 실기기 없음, iOS 기기는 `unavailable`로 strict runner 조건을 충족하지 못한다.
- Release E2E evidence scaffold: `python3 client/scripts/create_release_e2e_evidence.py --output docs/release-e2e-evidence.json`는 현재 git revision, device env, artifact path, 모든 required scenario key를 포함한 JSON을 생성한다. 생성 직후 scenario는 `pass: false`라 strict readiness를 통과할 수 없고, 실제 물리 기기 관측값을 채워야만 최종 release evidence가 된다.

### 2026-06-15 DB 마이그레이션 실행 게이트 보강

- `backend/tests/test_device_token_migration.py`가 임시 SQLite DB에 `DATABASE_URL=sqlite+aiosqlite:///...`를 주입하고 `python -m alembic upgrade head`를 실제 실행한다.
- 실행 후 `device_tokens.device_id`, `ix_device_tokens_device_id`, `ix_device_tokens_user_device_id`, `alembic_version=003_add_device_id_to_device_tokens`를 SQLite PRAGMA/쿼리로 검증한다.
- 검증: `venv/bin/python -m pytest -o addopts="" backend/tests/test_device_token_migration.py -q` -> `6 passed, 5 warnings`.

---

*SPEC ID: SPEC-MOBILE-004*
*생성일: 2026-06-13*
*상태: completed*
