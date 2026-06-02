---
id: SPEC-MOBILE-001
version: "1.0.0"
status: completed
created: "2026-03-22"
updated: "2026-06-03"
author: kisoo
priority: medium
issue_number: 0
---

# SPEC-MOBILE-001: iOS/Android 네이티브 앱 최적화 (MVP)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-22 | 초안 작성 | kisoo |
| 1.0.1 | 2026-06-03 | 구현 완료 및 Sync | kisoo |

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
| 개발 환경 | macOS (M1 MacBook Pro), Xcode 15+, Android Studio |

---

## 2. 가정 (Assumptions)

- iOS 빌드는 이미 동작 중이다 (client/ios/storage/temp에 녹음 파일 존재).
- Android 플랫폼 디렉토리가 존재하지 않으므로 `flutter create --platforms=android .`로 생성해야 한다.
- Firebase 프로젝트는 아직 생성되지 않았으며, Push 알림을 위해 새로 설정해야 한다.
- Apple Developer 계정이 사용 가능하다 (Push 알림 인증서, App Store 배포용).
- 백엔드 서버는 Tailscale VPN을 통해 접근하며, Celery 작업 완료 시 FCM API를 호출하도록 확장한다.
- 오프라인 STT 처리는 MVP 범위에서 제외한다.

---

## 3. 요구사항 (Requirements)

### REQ-MOBILE-001: iOS/Android 빌드 설정 (아이콘, 스플래시, 번들 ID)

**EARS 형식**: 시스템이 iOS/Android에서 빌드될 때, 시스템은 커스텀 앱 아이콘과 스플래시 스크린을 표시하며, 플랫폼별 번들 ID가 올바르게 설정되어야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-001-01 | `flutter_launcher_icons` 패키지로 1024x1024 소스 이미지에서 iOS/Android 앱 아이콘을 자동 생성한다 | P1 |
| REQ-MOBILE-001-02 | `flutter_native_splash` 패키지로 네이티브 스플래시 스크린을 설정한다 (앱 로고 + 배경색) | P1 |
| REQ-MOBILE-001-03 | iOS 번들 ID를 `com.voicetextnote.app`으로 설정한다 | P1 |
| REQ-MOBILE-001-04 | Android applicationId를 `com.voicetextnote.app`으로 설정한다 | P1 |
| REQ-MOBILE-001-05 | Android 플랫폼 디렉토리를 생성한다 (`flutter create --platforms=android .`) | P1 |
| REQ-MOBILE-001-06 | Android minSdkVersion을 29 (Android 10), targetSdkVersion을 34 (Android 14)로 설정한다 | P1 |

---

### REQ-MOBILE-002: Push 알림 (FCM/APNs)

**EARS 형식**: 회의록 처리 파이프라인이 완료되었을 때, 시스템은 사용자 디바이스에 Push 알림을 전송하여 결과를 확인하도록 안내해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-002-01 | Firebase 프로젝트를 생성하고 iOS/Android 앱을 등록한다 | P1 |
| REQ-MOBILE-002-02 | `firebase_messaging` 패키지를 통합하여 FCM 토큰을 수신한다 | P1 |
| REQ-MOBILE-002-03 | 앱 시작 시 FCM 토큰을 백엔드 서버에 등록한다 | P1 |
| REQ-MOBILE-002-04 | 백엔드 Celery 작업 완료 시 FCM HTTP v1 API를 통해 Push 알림을 전송한다 | P1 |
| REQ-MOBILE-002-05 | `flutter_local_notifications`로 포그라운드 상태에서도 알림을 표시한다 | P2 |
| REQ-MOBILE-002-06 | Push 알림 탭 시 해당 회의록 상세 화면으로 딥링크 네비게이션한다 | P2 |

---

### REQ-MOBILE-003: 백그라운드 오디오 녹음

**EARS 형식**: 사용자가 녹음 중에 앱을 백그라운드로 전환했을 때, 시스템은 녹음을 중단하지 않고 계속 진행해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-003-01 | iOS Info.plist에 `UIBackgroundModes: audio`를 추가한다 | P1 |
| REQ-MOBILE-003-02 | Android에서 `Foreground Service`(MICROPHONE 타입)를 구현하여 백그라운드 녹음을 지원한다 | P1 |
| REQ-MOBILE-003-03 | 백그라운드 녹음 중 상태바에 녹음 인디케이터를 표시한다 (iOS: 오렌지 도트, Android: Notification) | P1 |
| REQ-MOBILE-003-04 | `audio_session` 패키지로 오디오 세션을 관리하여 다른 앱 오디오와의 충돌을 방지한다 | P2 |
| REQ-MOBILE-003-05 | 앱이 시스템에 의해 종료(kill)되었을 때 녹음 파일이 손실되지 않도록 주기적으로 flush한다 | P2 |

---

### REQ-MOBILE-004: 플랫폼별 권한 관리

**EARS 형식**: 앱이 실행될 때, 시스템은 필요한 플랫폼 권한을 적절한 시점에 요청하고, 권한 거부 시 사용자에게 안내해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-004-01 | iOS에서 마이크 권한(`NSMicrophoneUsageDescription`)을 녹음 시작 전에 요청한다 (이미 설정됨) | P1 |
| REQ-MOBILE-004-02 | Android에서 `RECORD_AUDIO`, `POST_NOTIFICATIONS` 런타임 권한을 요청한다 | P1 |
| REQ-MOBILE-004-03 | 권한 거부 시 왜 권한이 필요한지 설명하는 다이얼로그를 표시한다 | P1 |
| REQ-MOBILE-004-04 | "다시 묻지 않기" 선택 후 설정 앱으로 이동하는 안내를 제공한다 | P2 |
| REQ-MOBILE-004-05 | `permission_handler` 패키지로 권한 상태를 통합 관리한다 | P2 |

---

### REQ-MOBILE-005: 앱 스토어 배포 준비 (메타데이터, 스크린샷)

**EARS 형식**: 앱이 앱 스토어에 제출될 때, 시스템은 App Store/Google Play 가이드라인에 부합하는 메타데이터와 스크린샷을 포함해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-005-01 | App Store Connect에 앱 정보(이름, 설명, 카테고리, 키워드)를 등록한다 | P2 |
| REQ-MOBILE-005-02 | Google Play Console에 앱 정보(이름, 설명, 카테고리)를 등록한다 | P2 |
| REQ-MOBILE-005-03 | iOS/Android 스크린샷을 각 디바이스 사이즈별로 준비한다 | P2 |
| REQ-MOBILE-005-04 | 개인정보 처리방침(Privacy Policy) URL을 설정한다 | P2 |
| REQ-MOBILE-005-05 | iOS: ATS(App Transport Security) 예외 사유를 문서화한다 (Tailscale HTTP 접속) | P2 |

---

### REQ-MOBILE-006: 딥링크 + 앱 내 네비게이션 최적화

**EARS 형식**: 사용자가 Push 알림 또는 외부 링크를 통해 앱에 진입했을 때, 시스템은 해당 콘텐츠 화면으로 직접 네비게이션해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-006-01 | Push 알림의 `meeting_id` payload를 파싱하여 회의록 상세 화면(`/summary/{meetingId}`)으로 이동한다 | P1 |
| REQ-MOBILE-006-02 | go_router의 딥링크 기능을 활용하여 `voicetextnote://summary/{meetingId}` URL scheme을 처리한다 | P2 |
| REQ-MOBILE-006-03 | 앱이 종료 상태에서 Push 알림으로 시작될 때 초기 라우팅을 올바르게 처리한다 | P2 |

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

변경 후:
  Flutter App (iOS/Android) → HTTP → FastAPI → Celery → FCM Push 알림
                                                      ↘ 결과 폴링 (fallback)
```

### 5.2 Push 알림 흐름

```
1. 앱 시작 → FCM 토큰 수신 → POST /api/v1/devices/register {fcm_token, platform}
2. 녹음 완료 → POST /api/v1/audio/upload → Celery 파이프라인 시작
3. Celery 파이프라인 완료 → FCM HTTP v1 API 호출 → 디바이스 Push 수신
4. Push 알림 탭 → 딥링크 → /summary/{meetingId} 화면
```

### 5.3 백그라운드 녹음 구현

**iOS**:
- Info.plist `UIBackgroundModes: [audio]` 추가
- `AVAudioSession.Category.playAndRecord` 설정
- `audio_session` 패키지로 세션 관리

**Android**:
- `Foreground Service` 타입 `MICROPHONE` 사용
- Notification Channel로 녹음 상태 표시
- `FOREGROUND_SERVICE_MICROPHONE` 권한 추가

### 5.4 디렉토리 구조 변경

```
client/
├── lib/
│   ├── services/
│   │   ├── push_notification_service.dart    # 신규: FCM 통합
│   │   └── permission_service.dart           # 신규: 권한 관리
│   ├── providers/
│   │   └── notification_provider.dart        # 신규: 알림 상태
│   └── config/
│       └── firebase_config.dart              # 신규: Firebase 설정
├── ios/
│   ├── Runner/
│   │   └── Info.plist                        # 수정: 백그라운드 모드 추가
│   ├── firebase_app_id_file.json             # 신규
│   └── GoogleService-Info.plist              # 신규
├── android/                                  # 신규: 전체 디렉토리
│   ├── app/
│   │   ├── src/main/
│   │   │   ├── AndroidManifest.xml
│   │   │   └── res/                          # 아이콘, 스플래시
│   │   └── build.gradle
│   └── google-services.json                  # 신규: Firebase
└── pubspec.yaml                              # 수정: 의존성 추가
```

---

## 6. 의존성 (Dependencies)

### 선행 SPEC

| SPEC | 상태 | 관계 |
|------|------|------|
| SPEC-APP-001 | 완료 | Flutter 기본 구조, 녹음 기능 |
| SPEC-STT-001 | 완료 | 백엔드 STT 파이프라인 |
| SPEC-SSE-001 | 완료 | 실시간 상태 업데이트 (Push 알림 fallback) |

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

### 외부 서비스

| 서비스 | 용도 | 설정 필요 |
|--------|------|----------|
| Firebase Console | FCM 프로젝트 생성, iOS/Android 앱 등록 | GoogleService-Info.plist, google-services.json |
| Apple Developer | Push 인증서 (APNs Key), 앱 번들 ID 등록 | .p8 키 파일 → Firebase에 업로드 |
| Google Play Console | Android 앱 등록 (배포 시) | 서명 키 생성 |

---

## Implementation Notes

### 구현 현황

**구현 날짜**: 2026-06-02

**진행 상태**: in-progress

### 구현된 기능

**완료됨 (Web + macOS)**:
- Flutter 3.24+ / Dart 3.5+ 업그레이드
- Web 빌드 지원 (Chrome, Safari)
- macOS 빌드 지원 (Intel + Apple Silicon)
- 오디오 녹음 (record 6.0+), 권한 요청 (permission_handler)
- Riverpod 2.6+ 상태관리, go_router 15.1+ 라우팅
- 백엔드 연동 (Dio 5.9+ HTTP 클라이언트)

**진행 중 (iOS/Android 네이티브 최적화)**:
- iOS 빌드 설정 (아이콘, 스플래시, 번들 ID)
- Android 플랫폼 추가 (`flutter create --platforms=android .`)
- Firebase Messaging (Push 알림)
- Push 알림 권한 요청
- 네이티브 성능 최적화

**제외됨 (MVP 범위 초과)**:
- 오프라인 STT 처리 (로컬 Whisper 모델)
- 백그라운드 오디오 녹음 (iOS/Android 제약)
- 다국어(i18n) 지원

### 기술 제약사항

**현재 제약**:
- Firebase 프로젝트 미생성 → Push 알림 미구현
- Apple Developer 계정 미사용 → App Store 배포 불가
- Android 플랫폼 디렉토리 없음 → Android 빌드 미검증

**추후 작업**:
- Firebase Console 프로젝트 생성
- APNs 인증서 발급 및 Firebase 연동
- iOS/Android 네이티브 테스트
- App Store / Play Store 배포

---

*SPEC ID: SPEC-MOBILE-001*
*생성일: 2026-03-22*
*상태: in-progress*
