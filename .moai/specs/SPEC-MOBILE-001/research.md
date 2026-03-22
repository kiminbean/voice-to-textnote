# SPEC-MOBILE-001: 리서치 결과

## 1. 현재 플랫폼 지원 현황

### 지원 플랫폼

| 플랫폼 | 상태 | 비고 |
|--------|------|------|
| Web (Chrome) | 활성 | 기본 개발/테스트 플랫폼 (`flutter run -d chrome`) |
| macOS | 활성 | 로컬 개발용 |
| iOS | 부분 지원 | Xcode 프로젝트 존재, Info.plist에 마이크 권한 설정됨, 실제 디바이스 빌드 이력 있음 (storage/temp에 m4a 파일 존재) |
| Android | 미지원 | `client/android/` 디렉토리 자체가 존재하지 않음 |

### iOS 현재 설정 분석

**Info.plist (client/ios/Runner/Info.plist)**:
- `NSMicrophoneUsageDescription`: "회의 녹음을 위해 마이크 접근이 필요합니다." (설정됨)
- `NSAppTransportSecurity > NSAllowsArbitraryLoads`: true (HTTP 허용, Tailscale IP 접속용)
- `CFBundleDisplayName`: "Voice TextNote"
- `UILaunchStoryboardName`: "LaunchScreen" (기본 Flutter 스플래시)
- 앱 아이콘: 커스텀 설정 없음 (기본 Flutter 아이콘)
- 백그라운드 모드: 미설정 (`UIBackgroundModes` 없음)
- Push 알림: 미설정

**iOS 빌드 증거**:
- `client/ios/storage/temp/`에 9개의 m4a 녹음 파일이 존재
- Pods 디렉토리에 `record_ios` scheme 존재 (CocoaPods 기반 빌드)
- Runner.xcodeproj/project.pbxproj 존재

### Android 현재 상태

- `client/android/` 디렉토리 없음
- Flutter 프로젝트 생성 시 `flutter create`로 Android 플랫폼 추가 필요
- AndroidManifest.xml 부재

---

## 2. 현재 녹음 구현 분석

### record 패키지 (v6.0.0)

**recording_provider.dart** 핵심 동작:
- `AudioRecorder` 클래스 사용 (record 패키지)
- 인코더: `AudioEncoder.aacLc` (AAC-LC, m4a 컨테이너)
- 저장 경로: `getApplicationDocumentsDirectory()` 기반
- 파일명 패턴: `meeting_{timestamp}.m4a`
- 권한 처리: `_recorder.hasPermission()` - iOS에서는 최초 호출 시 시스템 다이얼로그 표시

**현재 한계점**:
- 백그라운드 녹음 미지원 (앱이 백그라운드로 가면 녹음 중단)
- 일시 정지(pause) 상태 enum은 있으나 실제 구현 없음
- 음량 레벨 실시간 표시 없음

### 앱 구성

**AppConfig (app_config.dart)**:
- API 서버: `http://100.110.255.105:8000/api/v1` (Tailscale IP 하드코딩)
- API 타임아웃: 30초
- 폴링 간격: 2초

---

## 3. 누락된 네이티브 기능

### 필수 (MVP)

| 기능 | iOS | Android | 현재 상태 |
|------|-----|---------|----------|
| 마이크 권한 | 설정됨 | 미설정 | iOS만 완료 |
| 백그라운드 오디오 녹음 | 미설정 | 미설정 | 앱 전환 시 녹음 중단됨 |
| Push 알림 (FCM/APNs) | 미설정 | 미설정 | 처리 완료 알림 없음 |
| 앱 아이콘 | 기본값 | N/A | 커스텀 아이콘 없음 |
| 스플래시 스크린 | 기본값 | N/A | 기본 Flutter 스플래시 |
| 파일 접근 권한 | 미설정 | N/A | 문서 파일 업로드용 |

### 추가 필요 권한

**iOS 추가 권한 (Info.plist)**:
- `UIBackgroundModes`: `audio` (백그라운드 녹음)
- `UIBackgroundModes`: `remote-notification` (Push 알림)
- `NSFileProtectionComplete` 제거 또는 조정 (백그라운드 파일 접근)

**Android 권한 (AndroidManifest.xml)**:
- `RECORD_AUDIO` (마이크)
- `WRITE_EXTERNAL_STORAGE` / `READ_EXTERNAL_STORAGE` (파일)
- `FOREGROUND_SERVICE` + `FOREGROUND_SERVICE_MICROPHONE` (백그라운드 녹음)
- `POST_NOTIFICATIONS` (Android 13+ Push 알림)
- `INTERNET` (네트워크)
- `RECEIVE_BOOT_COMPLETED` (선택, 서비스 자동 시작)

---

## 4. 기술 권장사항

### Android 플랫폼 추가

```bash
# Flutter 프로젝트에 Android 플랫폼 추가
cd client
flutter create --platforms=android .
```

### 백그라운드 오디오 녹음

**추천 접근법**: `audio_session` 패키지 + 플랫폼별 설정
- iOS: `UIBackgroundModes` + `AVAudioSession` 카테고리 설정
- Android: `Foreground Service` + `MediaRecorder`
- record 패키지가 기본적으로 이를 지원하지만 플랫폼 설정이 필요

### Push 알림

**추천 스택**:
- `firebase_messaging` (FCM 기반 크로스 플랫폼)
- `flutter_local_notifications` (로컬 알림 표시)
- 백엔드에서 Celery 작업 완료 시 FCM API 호출

### 앱 아이콘 및 스플래시

**추천 패키지**:
- `flutter_launcher_icons` - 단일 소스 이미지에서 iOS/Android 아이콘 자동 생성
- `flutter_native_splash` - 네이티브 스플래시 스크린 설정

### 딥링크

- `go_router`가 이미 딥링크를 지원 (`path` 기반 라우팅)
- iOS: Universal Links (apple-app-site-association)
- Android: App Links (assetlinks.json)

---

## 5. 의존성 현황

### 현재 의존성 (pubspec.yaml)

| 패키지 | 버전 | 용도 |
|--------|------|------|
| flutter_riverpod | ^2.6.1 | 상태관리 |
| dio | ^5.9.2 | HTTP 클라이언트 |
| go_router | ^15.1.2 | 라우팅 |
| record | ^6.0.0 | 오디오 녹음 |
| path_provider | ^2.1.0 | 파일 경로 |
| intl | ^0.20.2 | 날짜/시간 포맷 |
| shimmer | ^3.0.0 | 로딩 UI |
| http | ^1.2.0 | HTTP (SSE용) |
| file_picker | ^8.0.0 | 파일 선택 |

### MVP에 추가 필요한 의존성

| 패키지 | 용도 | 우선순위 |
|--------|------|---------|
| firebase_core | Firebase 초기화 | 높음 |
| firebase_messaging | FCM Push 알림 | 높음 |
| flutter_local_notifications | 로컬 알림 표시 | 높음 |
| flutter_launcher_icons | 앱 아이콘 생성 | 높음 |
| flutter_native_splash | 스플래시 스크린 | 중간 |
| permission_handler | 권한 관리 통합 | 중간 |
| audio_session | 오디오 세션 관리 | 높음 |

---

## 6. 리스크 분석

| 리스크 | 영향도 | 대응 |
|--------|--------|------|
| Android 디렉토리 부재 | 높음 | `flutter create --platforms=android .`로 생성 |
| Firebase 프로젝트 미설정 | 중간 | Firebase Console에서 iOS/Android 앱 등록 필요 |
| Apple Developer 계정 필요 | 높음 | Push 알림, App Store 배포에 필수 |
| 백그라운드 녹음 OS 제한 | 중간 | iOS는 비교적 엄격, Android는 Foreground Service로 안정적 |
| Tailscale IP 하드코딩 | 낮음 | 환경 설정으로 분리 필요 (이미 AppConfig에 집중) |
