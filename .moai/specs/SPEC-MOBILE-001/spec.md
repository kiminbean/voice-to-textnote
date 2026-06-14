---
id: SPEC-MOBILE-001
version: "2.0.0"
status: completed
created: "2026-03-22"
updated: "2026-06-07"
author: kisoo
priority: medium
issue_number: 12
---

# SPEC-MOBILE-001: iOS/Android 네이티브 앱 최적화 (MVP)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-22 | 초안 작성 | kisoo |
| 1.0.1 | 2026-06-03 | 구현 완료 및 Sync | kisoo |
| 2.0.0 | 2026-06-06 | v2.0.0 전면 개정 — Firebase Admin SDK, DB persistence, 딥링크/콜드스타트, Celery hooks 추가 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter 3.24+ / Dart 3.5+ |
| 상태관리 | Riverpod 2.6+ (flutter_riverpod) |
| 오디오 녹음 | record 6.0+ |
| Push 알림 | firebase_messaging + flutter_local_notifications |
| 라우팅 | go_router 15.1+ |
| 대상 플랫폼 | iOS 15+, Android 10+ (API 29+) |
| 백엔드 | FastAPI (Tailscale VPN 경유) |
| 백엔드 Push | Firebase Admin SDK (Python, firebase-admin) |
| 데이터베이스 | PostgreSQL (device_tokens 테이블 persistence) |
| 작업 큐 | Celery (on_success/on_failure hook) |
| 개발 환경 | macOS (M4 Mac mini), Xcode 15+, Android Studio |

---

## 2. 가정 (Assumptions)

- iOS 빌드는 이미 동작 중이다 (client/ios/storage/temp에 녹음 파일 존재).
- Android 플랫폼 디렉토리가 존재하지 않으므로 `flutter create --platforms=android .`로 생성해야 한다.
- Firebase 프로젝트는 아직 생성되지 않았으며, Push 알림을 위해 새로 설정해야 한다.
- Apple Developer 계정이 사용 가능하다 (Push 알림 인증서, App Store 배포용).
- 백엔드 서버는 Tailscale VPN을 통해 접근하며, Celery 작업 완료 시 Firebase Admin SDK를 통해 FCM Push 알림을 전송한다.
- FCM 토큰은 메모리가 아닌 PostgreSQL DB에 영속 저장하여 서버 재시작 시에도 토큰이 유지된다.
- 오프라인 STT 처리는 MVP 범위에서 제외한다.

---

## 3. 요구사항 (Requirements)

### REQ-MOBILE-001: iOS/Android 빌드 설정 (아이콘, 스플래시, 번들 ID) [EXISTING]

**EARS 형식**: 시스템이 iOS/Android에서 빌드될 때, 시스템은 커스텀 앱 아이콘과 스플래시 스크린을 표시하며, 플랫폼별 번들 ID가 올바르게 설정되어야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-001-01 | `flutter_launcher_icons` 패키지로 1024x1024 소스 이미지에서 iOS/Android 앱 아이콘을 자동 생성한다 | P1 | [EXISTING] |
| REQ-MOBILE-001-02 | `flutter_native_splash` 패키지로 네이티브 스플래시 스크린을 설정한다 (앱 로고 + 배경색) | P1 | [EXISTING] |
| REQ-MOBILE-001-03 | iOS 번들 ID를 `com.voicetextnote.app`으로 설정한다 | P1 | [EXISTING] |
| REQ-MOBILE-001-04 | Android applicationId를 `com.voicetextnote.app`으로 설정한다 | P1 | [EXISTING] |
| REQ-MOBILE-001-05 | Android 플랫폼 디렉토리를 생성한다 (`flutter create --platforms=android .`) | P1 | [EXISTING] |
| REQ-MOBILE-001-06 | Android minSdkVersion을 29 (Android 10), targetSdkVersion을 34 (Android 14)로 설정한다 | P1 | [EXISTING] |

---

### REQ-MOBILE-002: Push 알림 — Firebase Admin SDK + DB Persistence [MODIFY]

**EARS 형식**: 회의록 처리 파이프라인이 완료되었을 때, 시스템은 Firebase Admin SDK를 통해 사용자 디바이스에 Push 알림을 전송하여 결과를 확인하도록 안내해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-01 | Firebase 프로젝트를 생성하고 iOS/Android 앱을 등록한다 | P1 | [EXISTING] |
| REQ-MOBILE-002-02 | `firebase_messaging` 패키지를 통합하여 FCM 토큰을 수신한다 | P1 | [EXISTING] |
| REQ-MOBILE-002-03 | 앱 시작 시 FCM 토큰을 백엔드 서버에 등록한다 (`POST /api/v1/devices/register`) | P1 | [EXISTING] |
| REQ-MOBILE-002-04 | 백엔드에서 `firebase-admin` Python 패키지를 사용하여 FCM HTTP v1 API로 Push 알림을 전송한다 (직접 HTTP 호출 대신 Admin SDK 사용) | P1 | [MODIFY] |
| REQ-MOBILE-002-05 | `flutter_local_notifications`로 포그라운드 상태에서도 알림을 표시한다 | P2 | [EXISTING] |
| REQ-MOBILE-002-06 | Push 알림 탭 시 해당 회의록 상세 화면으로 딥링크 네비게이션한다 | P2 | [EXISTING] |
| REQ-MOBILE-002-07 | FCM 디바이스 토큰을 PostgreSQL `device_tokens` 테이블에 영속 저장하여 서버 재시작 시에도 토큰이 유지된다 | P1 | [NEW] |
| REQ-MOBILE-002-08 | Celery 작업 완료 시 `on_success` hook에서 `meeting_id`를 포함한 payload로 Push 알림을 전송한다 | P1 | [NEW] |
| REQ-MOBILE-002-09 | Celery 작업 실패 시 `on_failure` hook에서 사용자에게 처리 실패 알림을 전송한다 | P2 | [NEW] |
| REQ-MOBILE-002-10 | 사용자 로그아웃 또는 토큰 만료 시 DB에서 해당 FCM 토큰을 무효화(invalidate)한다 | P1 | [NEW] |
| REQ-MOBILE-002-11 | Push 알림 payload에 `meeting_id` 필드를 포함하여 딥링크 타겟을 명확히 한다 | P1 | [NEW] |

---

### REQ-MOBILE-003: 백그라운드 오디오 녹음 [EXISTING]

**EARS 형식**: 사용자가 녹음 중에 앱을 백그라운드로 전환했을 때, 시스템은 녹음을 중단하지 않고 계속 진행해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-003-01 | iOS Info.plist에 `UIBackgroundModes: audio`를 추가한다 | P1 | [EXISTING] |
| REQ-MOBILE-003-02 | Android에서 `Foreground Service`(MICROPHONE 타입)를 구현하여 백그라운드 녹음을 지원한다 | P1 | [EXISTING] |
| REQ-MOBILE-003-03 | 백그라운드 녹음 중 상태바에 녹음 인디케이터를 표시한다 (iOS: 오렌지 도트, Android: Notification) | P1 | [EXISTING] |
| REQ-MOBILE-003-04 | `audio_session` 패키지로 오디오 세션을 관리하여 다른 앱 오디오와의 충돌을 방지한다 | P2 | [EXISTING] |
| REQ-MOBILE-003-05 | 앱이 시스템에 의해 종료(kill)되었을 때 녹음 파일이 손실되지 않도록 주기적으로 flush한다 | P2 | [EXISTING] |

**검증 참고**: 백그라운드 녹음은 iOS/Android 모두 OS 수준의 메모리 압박으로 프로세스가 종료될 수 있으므로, REQ-MOBILE-003-05의 flush 간격은 10초 이하로 설정한다. flush 간격이 길면 강제 종료 시 데이터 손실 구간이 커진다.

---

### REQ-MOBILE-004: 플랫폼별 권한 관리 [EXISTING]

**EARS 형식**: 앱이 실행될 때, 시스템은 필요한 플랫폼 권한을 적절한 시점에 요청하고, 권한 거부 시 사용자에게 안내해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-004-01 | iOS에서 마이크 권한(`NSMicrophoneUsageDescription`)을 녹음 시작 전에 요청한다 (이미 설정됨) | P1 | [EXISTING] |
| REQ-MOBILE-004-02 | Android에서 `RECORD_AUDIO`, `POST_NOTIFICATIONS` 런타임 권한을 요청한다 | P1 | [EXISTING] |
| REQ-MOBILE-004-03 | 권한 거부 시 왜 권한이 필요한지 설명하는 다이얼로그를 표시한다 | P1 | [EXISTING] |
| REQ-MOBILE-004-04 | "다시 묻지 않기" 선택 후 설정 앱으로 이동하는 안내를 제공한다 | P2 | [EXISTING] |
| REQ-MOBILE-004-05 | `permission_handler` 패키지로 권한 상태를 통합 관리한다 | P2 | [EXISTING] |

---

### REQ-MOBILE-005: 앱 스토어 배포 준비 (메타데이터, 스크린샷) [EXISTING]

**EARS 형식**: 앱이 앱 스토어에 제출될 때, 시스템은 App Store/Google Play 가이드라인에 부합하는 메타데이터와 스크린샷을 포함해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-005-01 | App Store Connect에 앱 정보(이름, 설명, 카테고리, 키워드)를 등록한다 | P2 | [EXISTING] |
| REQ-MOBILE-005-02 | Google Play Console에 앱 정보(이름, 설명, 카테고리)를 등록한다 | P2 | [EXISTING] |
| REQ-MOBILE-005-03 | iOS/Android 스크린샷을 각 디바이스 사이즈별로 준비한다 | P2 | [EXISTING] |
| REQ-MOBILE-005-04 | 개인정보 처리방침(Privacy Policy) URL을 설정한다 | P2 | [EXISTING] |
| REQ-MOBILE-005-05 | iOS: ATS(App Transport Security) 예외 사유를 문서화한다 (Tailscale HTTP 접속) | P2 | [EXISTING] |

---

### REQ-MOBILE-006: 딥링크 + 앱 내 네비게이션 최적화 [MODIFY]

**EARS 형식**: 사용자가 Push 알림 또는 외부 링크를 통해 앱에 진입했을 때, 시스템은 해당 콘텐츠 화면으로 직접 네비게이션해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-006-01 | Push 알림의 `meeting_id` payload를 파싱하여 회의록 상세 화면(`/summary/{meetingId}`)으로 이동한다 | P1 | [EXISTING] |
| REQ-MOBILE-006-02 | iOS Custom URL Scheme `voicetextnote://` 를 Info.plist에 등록하고, Android Intent Filter를 AndroidManifest.xml에 등록한다 | P1 | [NEW] |
| REQ-MOBILE-006-03 | go_router의 `initialUri` 처리를 통해 딥링크 URL을 라우팅에 매핑한다 (`voicetextnote://summary/{id}` → `/summary/{id}`) | P1 | [NEW] |
| REQ-MOBILE-006-04 | 앱이 완전히 종료(cold start)된 상태에서 Push 알림으로 시작될 때, Firebase `getInitialMessage()`를 통해 초기 라우팅을 올바르게 처리한다 | P1 | [NEW] |
| REQ-MOBILE-006-05 | 앱이 백그라운드에 있을 때 Push 알림으로 resume되는 경우 `onMessageOpenedApp` 스트림을 통해 라우팅한다 | P1 | [NEW] |
| REQ-MOBILE-006-06 | 딥링크 대상 meetingId가 존재하지 않거나 유효하지 않은 경우 에러 화면으로 fallback한다 | P2 | [NEW] |

---

## 4. MVP 범위에서 제외

| 기능 | 제외 사유 | 향후 SPEC |
|------|----------|----------|
| Apple Watch / WearOS 연동 | 핵심 기능 아님, 사용자 수요 미확인 | SPEC-MOBILE-002 |
| iOS Widget / Android Widget | MVP 이후 UX 개선 단계 | SPEC-MOBILE-003 |
| Siri / Google Assistant 통합 | 음성 명령 지원은 향후 | SPEC-MOBILE-004 |
| 오프라인 STT 처리 | 온디바이스 모델 크기/성능 문제 | SPEC-MOBILE-005 |
| TestFlight / Internal Testing 자동화 | CI/CD 파이프라인 별도 구성 | SPEC-CI-001 |
| 다국어(i18n) | 별도 SPEC으로 분리 | SPEC-I18N-001 |

---

## 5. 기술 설계

### 5.1 아키텍처 변경

```
현재:
  Flutter App (Web/macOS) → HTTP → FastAPI → Celery → 결과 폴링

변경 후 (v2.0.0):
  Flutter App (iOS/Android) → HTTP → FastAPI → Celery → Firebase Admin SDK → FCM Push
                        ↓                                      ↓
                  FCM Token 등록                        DB (device_tokens)
                  POST /devices/register                      ↑
                                                       영속 저장 (서버 재시작 유지)
```

### 5.2 Push 알림 흐름 (Firebase Admin SDK 기반)

```
1. 앱 시작 → FCM 토큰 수신 → POST /api/v1/devices/register {fcm_token, platform, user_id}
2. 백엔드 → device_tokens 테이블에 토큰 영속 저장 (UPSERT)
3. 녹음 완료 → POST /api/v1/audio/upload → Celery 파이프라인 시작
4. Celery on_success hook → Firebase Admin SDK → messaging.send({
     token: fcm_token,
     notification: { title: "회의록 처리 완료", body: "..." },
     data: { meeting_id: str }
   })
5. 디바이스 Push 수신 → payload 파싱 → go_router 네비게이션 → /summary/{meetingId}
6. Celery on_failure hook → Firebase Admin SDK → 에러 알림 전송
```

### 5.3 DB Persistence — device_tokens 스키마

```sql
CREATE TABLE device_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    fcm_token VARCHAR NOT NULL UNIQUE,
    platform VARCHAR NOT NULL,       -- 'ios' | 'android'
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);

-- 사용자별 활성 토큰 조회
CREATE INDEX idx_device_tokens_user_active ON device_tokens(user_id, is_active);
```

### 5.4 Celery Hook 설계

```python
# backend/app/services/push_service.py
class PushService:
    def __init__(self):
        # Firebase Admin SDK 초기화 (서비스 계정 키)
        firebase_admin.initialize_app(credentials.Certificate("path/to/serviceAccountKey.json"))

    async def send_push(self, user_id: str, meeting_id: str, status: str):
        tokens = await self._get_active_tokens(user_id)
        for token in tokens:
            message = messaging.Message(
                notification=messaging.Notification(
                    title="회의록 처리 완료" if status == "success" else "처리 실패",
                    body="...",
                ),
                data={"meeting_id": meeting_id},
                token=token,
            )
            messaging.send(message)

    async def invalidate_token(self, fcm_token: str):
        """FCM 토큰 무효화 (FCM 응답이 UNREGISTERED인 경우)"""
        ...
```

### 5.5 백그라운드 녹음 구현

**iOS**:
- Info.plist `UIBackgroundModes: [audio]` 추가
- `AVAudioSession.Category.playAndRecord` 설정
- `audio_session` 패키지로 세션 관리

**Android**:
- `Foreground Service` 타입 `MICROPHONE` 사용
- Notification Channel로 녹음 상태 표시
- `FOREGROUND_SERVICE_MICROPHONE` 권한 추가

### 5.6 딥링크 아키텍처

```
Push 알림 탭
  ├── Cold start (앱 종료 상태)
  │   └── FirebaseMessaging.instance.getInitialMessage()
  │       └── message?.data['meeting_id'] → go_router initialUri
  ├── Background (앱 백그라운드)
  │   └── FirebaseMessaging.onMessageOpenedApp.listen()
  │       └── message.data['meeting_id'] → context.go('/summary/$id')
  └── Foreground
      └── flutter_local_notifications onDidReceiveNotificationResponse
          └── response.payload → context.go('/summary/$id')

URL Scheme (외부 링크)
  ├── iOS: voicetextnote://summary/{id} (Info.plist CFBundleURLSchemes)
  ├── Android: voicetextnote://summary/{id} (AndroidManifest intent-filter)
  └── go_router: initialUri / deepLink 처리
```

### 5.7 디렉토리 구조 변경

```
client/
├── lib/
│   ├── services/
│   │   ├── push_notification_service.dart    # FCM 통합, 토큰 관리, 메시지 핸들링
│   │   ├── deep_link_service.dart            # [NEW] 딥링크 파싱, 콜드스타트 처리
│   │   └── permission_service.dart           # 권한 관리
│   ├── providers/
│   │   └── notification_provider.dart        # 알림 상태 (Riverpod)
│   └── config/
│       └── firebase_config.dart              # Firebase 설정
├── ios/
│   ├── Runner/
│   │   ├── Info.plist                        # 백그라운드 모드 + URL Scheme + Push 설정
│   │   └── Runner.entitlements               # [NEW] Push Notification entitlement
│   ├── firebase_app_id_file.json             # [NEW]
│   └── GoogleService-Info.plist              # [NEW]
├── android/                                  # 전체 디렉토리 신규
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── AndroidManifest.xml           # Foreground Service + intent-filter + 권한
│   │   │   └── res/                          # 아이콘, 스플래시
│   │   └── build.gradle
│   └── google-services.json                  # Firebase
└── pubspec.yaml                              # 의존성 추가

backend/
├── app/
│   ├── services/
│   │   └── push_service.py                   # [NEW] Firebase Admin SDK Push 전송
│   ├── api/
│   │   └── v1/
│   │       └── routes/
│   │           └── devices.py                # [NEW] 디바이스 토큰 등록/조회 API
│   ├── models/
│   │   └── device_token.py                   # [NEW] SQLAlchemy device_tokens 모델
│   └── workers/
│       └── hooks/
│           └── celery_push_hooks.py          # [NEW] on_success/on_failure Push hook
└── alembic/
    └── versions/
        └── xxx_add_device_tokens.py          # [NEW] 마이그레이션
```

---

## 6. 의존성 (Dependencies)

### 선행 SPEC

| SPEC | 상태 | 관계 |
|------|------|------|
| SPEC-APP-001 | 완료 | Flutter 기본 구조, 녹음 기능 |
| SPEC-STT-001 | 완료 | 백엔드 STT 파이프라인 |
| SPEC-SSE-001 | 완료 | 실시간 상태 업데이트 (Push 알림 fallback) |
| SPEC-REFACTOR-001 | 완료 | 라우터 도메인 그룹핑, 에러 헬퍼 |

### 추가 의존성 (pubspec.yaml)

```yaml
dependencies:
  firebase_core: ^3.8.0
  firebase_messaging: ^15.1.0
  flutter_local_notifications: ^18.0.0
  audio_session: ^0.1.21
  permission_handler: ^11.3.0

dev_dependencies:
  flutter_launcher_icons: ^0.14.2
  flutter_native_splash: ^2.4.0
```

### 백엔드 의존성 (requirements.txt / pyproject.toml)

```
firebase-admin>=6.5.0       # Firebase Admin SDK — FCM 전송용
```

### 외부 서비스

| 서비스 | 용도 | 설정 필요 |
|--------|------|----------|
| Firebase Console | FCM 프로젝트 생성, iOS/Android 앱 등록 | GoogleService-Info.plist, google-services.json |
| Firebase Admin SDK | 서비스 계정 키 (서버 측 FCM 전송) | serviceAccountKey.json → 백엔드 환경변수 |
| Apple Developer | Push 인증서 (APNs Key), 앱 번들 ID 등록 | .p8 키 파일 → Firebase에 업로드 |
| Google Play Console | Android 앱 등록 (배포 시) | 서명 키 생성 |

---

## Implementation Notes

### 구현 현황

**버전**: v2.0.0

**진행 상태**: in-progress (Phase A/B/C 구현 완료, Phase D/E 대기)

### v1.0.0에서 구현된 기능

**완료됨 (Web + macOS)**:
- Flutter 3.24+ / Dart 3.5+ 업그레이드
- Web 빌드 지원 (Chrome, Safari)
- macOS 빌드 지원 (Intel + Apple Silicon)
- 오디오 녹음 (record 6.0+), 권한 요청 (permission_handler)
- Riverpod 2.6+ 상태관리, go_router 15.1+ 라우팅
- 백엔드 연동 (Dio 5.9+ HTTP 클라이언트)

### v2.0.0에서 신규/수정되는 기능

**백엔드 인프라 (Phase A) — 구현 완료**:
- `device_tokens` DB 테이블 및 SQLAlchemy 모델 생성 (`backend/db/device_token_models.py`)
- Alembic 마이그레이션 `002_add_device_tokens.py` 작성
- `PushService` 클래스 구현 — Firebase Admin SDK 통합, send_to_user/send_to_token/invalidate_token
- 디바이스 토큰 등록/조회 API (`backend/app/api/v1/auth/devices.py` 수정)
- Celery `on_success`/`on_failure` Push hook (`backend/app/workers/hooks/celery_push_hooks.py`)
- 테스트: `test_device_token_models.py` (247줄), `test_device_token_migration.py` (87줄), `test_push_service_db.py` (261줄)

**iOS Push 설정 (Phase B) — 구현 완료**:
- Info.plist에 `UIBackgroundModes: remote-notification` 추가
- URL Scheme `voicetextnote` 등록 (CFBundleURLSchemes)

**딥링크 + 네비게이션 (Phase C) — 구현 완료**:
- iOS: `voicetextnote://` URL Scheme (CFBundleURLSchemes)
- Android: Intent Filter (`voicetextnote://` scheme) — AndroidManifest.xml 수정
- `DeepLinkService` 클래스 (`client/lib/services/deep_link_service.dart`, 180줄)
  - URL 파싱, cold start/background/foreground 처리
  - 에러 fallback (유효하지 않은 URL → 에러 화면)
- go_router 딥링크 통합 (`client/lib/router/app_router.dart` 수정)

**App Store 준비 (Phase D) — 자동화 준비 완료 / 외부 등록 대기**:
- iOS no-codesign device build 검증 완료: `cd client && ./scripts/verify_mobile.sh --native` -> `Built build/ios/iphoneos/Runner.app`
- Android debug APK 검증 완료: `Built build/app/outputs/flutter-apk/app-debug.apk`
- 실제 App Store Connect 등록, provisioning profile, TestFlight 배포는 Apple Developer 계정과 서명 자산 필요.

**통합 테스트 (Phase E) — 코드/빌드 검증 완료 / Push E2E 대기**:
- Firebase client/backend wiring과 테스트는 backend 전체 suite 및 Flutter 전체 suite에 포함되어 통과.
- Device token persistence 보강: `device_tokens.device_id` migration과 `(user_id, device_id)` 기반 unregister를 추가해 다중 기기에서 요청한 기기만 비활성화되도록 고정했다. `venv/bin/python -m pytest -o addopts="" backend/tests/unit/test_devices_api_coverage.py backend/tests/test_push_service_db.py backend/tests/test_device_token_migration.py -q` -> `25 passed`.
- Release readiness 기본 사전검사 추가: `python3 client/scripts/verify_release_readiness.py`는 Firebase config, APNs entitlement, App Store metadata, backend Push wiring, E2E checklist를 정적 검증한다.
- Strict release readiness: `python3 client/scripts/verify_release_readiness.py --strict`는 release 문서 placeholder 제거, `FIREBASE_CREDENTIALS_PATH`, APNs key, App Store Connect API key, Android/iOS 실기기 식별자, 테스트 FCM token을 요구하고, Android serial은 `adb devices -l`, iOS UDID는 `xcrun devicectl list devices`에서 실제 연결/available 상태인지 확인한다.
- 실제 FCM/APNs Push 수신, cold-start 딥링크, 실기기 백그라운드 흐름은 Firebase 프로젝트, APNs key, 서비스 계정, iOS/Android 실기기 필요.

**제외됨 (MVP 범위 초과)**:
- 오프라인 STT 처리 (로컬 Whisper 모델)
- 다국어(i18n) 지원

### 기술 제약사항

**현재 제약**:
- Firebase 프로젝트/서비스 계정/APNs key가 현재 세션에 제공되지 않음 → Push 알림 E2E 테스트 불가 (코드와 빌드는 검증 완료)
- Apple Developer 계정 미사용 → App Store 배포 불가
- Firebase Admin SDK 서비스 계정 키 미제공 → 실제 Push 전송 불가

**Phase D/E 진입 조건**:
- Firebase Console 프로젝트 생성 + iOS/Android 앱 등록
- Firebase 서비스 계정 키 발급 → 백엔드 환경변수 등록
- APNs 인증서 발급 및 Firebase 연동
- iOS/Android 실기기 테스트
- `device_tokens` DB 마이그레이션 실행 (alembic upgrade head)

---

*SPEC ID: SPEC-MOBILE-001*
*생성일: 2026-03-22*
*상태: completed (v2.0.0 — Phase A/B/C 구현 완료, Phase D/E 후속 SPEC 분리)*
