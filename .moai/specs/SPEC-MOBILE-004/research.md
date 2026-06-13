# Research: SPEC-MOBILE-004 — 모바일 프로덕션 완성

## 연구 목적

SPEC-MOBILE-001 v2.0.0의 Phase A/B/C 구현 완료 후, 미구현된 Phase D (App Store 배포 준비)와 Phase E (Firebase 실제 연동 및 E2E 테스트)를 완성한다. 동시에 심층 코드 분석을 통해 기존 구현의 결함(데드 코드, 버그)을 식별하고 수정한다.

---

## 1. 아키텍처 분석

### 1.1 Flutter 클라이언트 구조

- **상태 관리**: Riverpod 2.6+ (Notifier/NotifierProvider + StateNotifier/StateNotifierProvider 혼용)
- **네비게이션**: go_router 15.1+ (auth redirect + 딥링크 통합)
- **HTTP**: Dio 5.9+ (JWT + guest token 인터셉터, 401 자동 refresh)
- **서비스 계층**: 33개 서비스, 18개 프로바이더, 12개 화면
- **테스트**: 55개 테스트 파일 (client/test/)

### 1.2 플랫폼별 네이티브 코드

#### iOS (`client/ios/Runner/`)
- **`AppDelegate.swift`** (19줄): 최소 구현. `GeneratedPluginRegistrant` 등록만. 네이티브 녹음/권한/알림 Swift 코드 없음. 모든 iOS 동작은 Flutter 플러그인에 의존 (`record`, `audio_session`, `firebase_messaging`, `permission_handler`).
- **`Info.plist`**: `UIBackgroundModes: ["audio", "remote-notification"]` 구성 완료. `NSMicrophoneUsageDescription` 설정됨. `voicetextnote://` URL Scheme 등록됨. `FirebaseAppDelegateProxyEnabled: false` (수동 FCM 처리).

#### Android (`client/android/app/src/main/`)
- **`AndroidManifest.xml`**: `RECORD_AUDIO`, `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_MICROPHONE`, `POST_NOTIFICATIONS` 권한 선언. `RecordingService` foregroundServiceType="microphone" 등록. 딥링크 intent-filter 등록.
- **`MainActivity.kt`**: MethodChannel `com.voicetextnote.app/recording` 처리 (startForegroundService, stopForegroundService, flushRecording).
- **`RecordingService.kt`**: Foreground Service 구현. notification channel `recording_channel` (IMPORTANCE_LOW), "녹음 중" 알림 표시. START_STICKY.
- **`WhisperSttPlugin.kt`**: DEPRECATED skeleton (whisper_ggml_plus로 대체됨).

#### MethodChannel 사용 (2개만 존재)
| 채널 | 방향 | 메서드 | 상태 |
|------|------|--------|------|
| `com.voicetextnote.app/recording` | Dart→Android | startForegroundService, stopForegroundService, flushRecording | Active (Android only) |
| `com.voicetextnote/whisper_stt` | Dart→Native | transcribe, isAvailable | DEPRECATED |

---

## 2. 핵심 발견사항 (Critical Findings)

### 2.1 Push 알림: 90% 스캐폴드, 0% 연동 (CRITICAL)

**PushNotificationService** (`push_notification_service.dart`, 141줄)와 **NotificationProvider** (`notification_provider.dart`) 코드는 작성되어 있으나 **런타임에서 호출되지 않음**.

| 컴포넌트 | 정의 위치 | 호출 여부 | 판정 |
|----------|----------|----------|------|
| `NotificationNotifier.initialize()` | notification_provider.dart:52 | **호출된 곳 없음** | 데드 코드 |
| `fcmTokenProvider` | notification_provider.dart:128 | **소비자 0건** | 토큰 획득 불가 |
| `registerFCMBackgroundHandler()` | push_notification_service.dart:139 | **호출된 곳 없음** | 백그라운드 핸들러 미등록 |
| `DeepLinkService.handleColdStart()` | deep_link_service.dart:49 | **호출 안됨** (main.dart가 별도 구현) | 중복 로직 |
| `DeepLinkService.handleBackgroundResume()` | deep_link_service.dart:66 | **호출 안됨** | onMessageOpenedApp 미구독 |
| `DeepLinkService.handleUrlScheme()` | deep_link_service.dart:90 | **호출 안됨** | URL Scheme 미처리 |

**백엔드 연동 갭**: `api_client.dart`에 FCM 토큰 헤더/등록 로직 없음. 어떤 서비스도 `/devices/register`를 호출하지 않음.

### 2.2 백엔드 Push 서비스: MOCK 모드

**PushService** (`backend/services/push_service.py`):
- `send_push()`: `[MOCK] FCM 전송` 로그만 출력, 실제 FCM 전송 코드는 주석 처리됨
- `_ensure_firebase_initialized()`: `firebase_admin.initialize_app()` 호출 없음
- `firebase-admin>=6.0` 의존성은 pyproject.toml에 선언됨

**Celery push hooks** (`backend/app/workers/hooks/celery_push_hooks.py`):
- `on_pipeline_success()` / `on_pipeline_failure()` 정의됨
- **실제 Celery 태스크에서 호출되는 곳 없음** (grep 결과 0건)
- 완전한 데드 코드

**Settings 누락**: `backend/app/config.py`에 `FIREBASE_CREDENTIALS_PATH` 등 Firebase 설정 필드 없음.

### 2.3 백그라운드 녹음: 작동은 하나 복원력 부족

**작동 중**: 
- iOS: `audio_session` 플러그인으로 백그라운드 오디오 세션 유지 (10초 간격 flush)
- Android: `RecordingService` Foreground Service로 녹음 유지

**결함**:
- 앱 강제 종료 시 녹음 파일 경로 손실 (crash recovery 없음)
- `pause/resume` 메서드 미구현 (`RecordingStatus.paused` enum은 존재)
- Android `flushRecording`이 no-op (`result.success(null)`)
- 백그라운드 완료 후 업로드 트리거 없음

### 2.4 권한 관리: 파편화 및 버그

**권한 서비스** (`permission_service.dart`):
- 마이크, 알림 권한만 처리
- 저장공간/미디어 권한 누락 (`Permission.storage`, `Permission.audio`)

**치명적 버그**: `permission_dialog.dart:145-168`에서 `openAppSettings()` → `openAppSettingsIOS()` → `openAppSettings()` **무한 재귀** 발생. 로컬 함수가 `PermissionService.openAppSettings`를 가림.

### 2.5 SSE vs Push 상호작용

현재 실시간 메커니즘은 SSE (Redis Pub/Sub):
```
Celery Task → publish_task_event() → Redis channel "task:{id}:status"
                                           ↓
                        SSE endpoint → 클라이언트 (foreground only)
```

SSE는 활성 HTTP 연결이 필요하므로 앱 백그라운드 시 연결 끊김. Push 알림(FCM)이 백그라운드 시나리오에 필요하나 현재 비기능 상태.

---

## 3. 기존 패턴 및 컨벤션

### 3.1 Riverpod 상태 관리 패턴
- `Notifier<XXXState>` (신규): recordingProvider, meetingListProvider
- `StateNotifier<XXXState>` (기존): notificationProvider, authStateProvider
- **일관성 권장**: 신규 코드는 `Notifier` 패턴 사용

### 3.2 Android MethodChannel 패턴
- `MainActivity.kt`에서 `MethodChannel` 핸들러 등록
- Foreground Service로 장시간 작업 처리
- `CoroutineScope`로 비동기 작업

### 3.3 백엔드 서비스 패턴
- `backend/services/`에 비즈니스 로직
- `backend/db/`에 SQLAlchemy 모델
- `backend/app/api/v1/`에 API 라우터
- `backend/app/workers/`에 Celery 태스크

---

## 4. 위험 및 제약사항

| 위험 | 영향도 | 완화 방안 |
|------|--------|----------|
| Firebase 프로젝트 미생성 | Push E2E 테스트 불가 | SPEC에 Firebase 설정 단계 포함, 설정 전까지는 코드 수준 wiring만 진행 |
| Apple Developer 계정 필요 | App Store 배포 불가 | Phase D의 메타데이터는 준비, 실제 등록은 수동 |
| iOS 실기기 테스트 필요 | Push/백그라운드 검증 | 시뮬레이터 한계 명시, 실기기 테스트 체크리스트 제공 |
| 권한 다이얼로그 무한 재귀 | 크래시 위험 | P0 우선수준으로 즉시 수정 |
| Celery hook 연동 | 기존 파이프라인 영향 | 기존 태스크 완료 로직에 hook 호출 추가, 회귀 테스트 필수 |

---

## 5. 구현 접근 권고사항

### 5.1 Push 알림 Wiring (최우선)
1. `main.dart`에서 `NotificationNotifier.initialize()` 호출
2. FCM 토큰 획득 후 백엔드 `/devices/register` 전송 (api_client.dart에 통합)
3. `registerFCMBackgroundHandler()` 호출 추가
4. `DeepLinkService` 핸들러를 main.dart/router에 연결
5. 백엔드 `push_service.py`에서 MOCK 코드를 실제 FCM 전송으로 교체
6. `config.py`에 `FIREBASE_CREDENTIALS_PATH` 추가
7. Celery 태스크 완료 지점에 `on_pipeline_success/on_failure` hook 호출 추가

### 5.2 백그라운드 녹음 강화
1. 녹음 파일 경로를 SharedPreferences/Hive에 주기적으로 저장 (crash recovery)
2. `RecordingProvider`에 `pauseRecording()`/`resumeRecording()` 추가
3. Android `flushRecording` 실제 flush 로직 구현
4. 백그라운드 완료 시 upload 트리거 (workmanager 또는 foreground service 확장)

### 5.3 권한 관리 수정
1. `permission_dialog.dart` 무한 재귀 버그 수정 (P0)
2. `PermissionService`에 저장공간/미디어 권한 추가
3. Android rationale-before-request 플로우 추가

### 5.4 App Store 준비 (Phase D)
1. App Store Connect / Google Play Console 메타데이터 템플릿
2. 디바이스별 스크린샷 촬영 가이드
3. 개인정보 처리방침 URL 설정
4. ATS 예외 사유 문서화

---

## 참조 파일

| 영역 | 파일 경로 |
|------|----------|
| Push 서비스 (Client) | `client/lib/services/push_notification_service.dart` |
| Push 프로바이더 | `client/lib/providers/notification_provider.dart` |
| 딥링크 서비스 | `client/lib/services/deep_link_service.dart` |
| 권한 서비스 | `client/lib/services/permission_service.dart` |
| 권한 다이얼로그 (버그) | `client/lib/widgets/permission_dialog.dart:145-168` |
| 녹음 서비스 | `client/lib/services/background_recording_service.dart` |
| 녹음 프로바이더 | `client/lib/providers/recording_provider.dart` |
| API 클라이언트 | `client/lib/services/api_client.dart` |
| iOS Info.plist | `client/ios/Runner/Info.plist` |
| Android Manifest | `client/android/app/src/main/AndroidManifest.xml` |
| Android RecordingService | `client/android/.../RecordingService.kt` |
| Push 서비스 (Backend) | `backend/services/push_service.py` |
| 디바이스 토큰 모델 | `backend/db/device_token_models.py` |
| 디바이스 API | `backend/app/api/v1/auth/devices.py` |
| Celery push hooks | `backend/app/workers/hooks/celery_push_hooks.py` |
| 백엔드 설정 | `backend/app/config.py` |
| SSE 이벤트 | `backend/events/publisher.py` |

---

*연구 수행: Sisyphus + Explore 병렬 에이전트*
*수행일: 2026-06-13*
