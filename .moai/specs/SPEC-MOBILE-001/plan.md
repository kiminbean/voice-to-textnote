# SPEC-MOBILE-001: 실행 계획

## Phase 1: 플랫폼 기반 설정 (REQ-MOBILE-001)

### Task 1.1: Android 플랫폼 생성
- `flutter create --platforms=android .` 실행
- minSdkVersion 29, targetSdkVersion 34 설정
- applicationId `com.voicetextnote.app` 설정
- 빌드 검증: `flutter build apk --debug`

### Task 1.2: iOS 빌드 설정 정비
- 번들 ID `com.voicetextnote.app` 확인/설정
- 배포 타겟 iOS 15.0으로 설정
- Xcode 프로젝트 Signing 설정 확인

### Task 1.3: 앱 아이콘 생성
- 1024x1024 소스 이미지 준비 (assets/icon/)
- `flutter_launcher_icons` 패키지 설정 (pubspec.yaml)
- iOS/Android 아이콘 자동 생성 실행
- 빌드 검증: 실제 디바이스에서 아이콘 확인

### Task 1.4: 스플래시 스크린 설정
- `flutter_native_splash` 패키지 설정
- 앱 로고 + 배경색 지정
- iOS/Android 네이티브 스플래시 생성
- 빌드 검증: 앱 시작 시 스플래시 표시 확인

**Phase 1 완료 기준**: iOS/Android 모두 커스텀 아이콘/스플래시로 빌드 성공

---

## Phase 2: 백그라운드 오디오 녹음 (REQ-MOBILE-003)

### Task 2.1: iOS 백그라운드 모드 설정
- Info.plist에 `UIBackgroundModes: [audio]` 추가
- `audio_session` 패키지 통합
- AVAudioSession 카테고리를 `playAndRecord`로 설정
- 검증: 앱을 백그라운드로 전환 후 녹음 지속 확인

### Task 2.2: Android Foreground Service 구현
- AndroidManifest.xml에 권한 추가 (FOREGROUND_SERVICE, FOREGROUND_SERVICE_MICROPHONE)
- Foreground Service Notification Channel 설정
- record 패키지의 Android Foreground Service 모드 활성화
- 검증: 앱을 백그라운드로 전환 후 녹음 지속 확인

### Task 2.3: 녹음 안전성 강화
- 녹음 중 주기적 flush 로직 추가 (앱 강제 종료 대비)
- 녹음 상태 복원 로직 (앱 재시작 시 미완료 녹음 파일 처리)

**Phase 2 완료 기준**: iOS/Android 모두 백그라운드에서 녹음 지속, 앱 전환 후 복귀 시 정상 동작

---

## Phase 3: Push 알림 (REQ-MOBILE-002)

### Task 3.1: Firebase 프로젝트 설정
- Firebase Console에서 프로젝트 생성
- iOS 앱 등록 → GoogleService-Info.plist 다운로드
- Android 앱 등록 → google-services.json 다운로드
- APNs Key(.p8) 생성 후 Firebase에 업로드

### Task 3.2: Flutter FCM 통합
- `firebase_core`, `firebase_messaging` 패키지 추가
- `PushNotificationService` 클래스 구현
  - FCM 토큰 수신
  - 포그라운드/백그라운드 메시지 핸들러
- `NotificationProvider` (Riverpod) 구현
- 검증: FCM 토큰 로그 출력, Firebase Console에서 테스트 메시지 전송

### Task 3.3: 백엔드 FCM 연동
- POST /api/v1/devices/register 엔드포인트 추가
- Celery 작업 완료 콜백에서 FCM HTTP v1 API 호출
- Firebase Admin SDK (Python) 통합
- 검증: 녹음 → 업로드 → 처리 완료 → Push 수신 E2E 테스트

### Task 3.4: 로컬 알림 + 딥링크
- `flutter_local_notifications` 패키지 통합
- 포그라운드 상태에서 알림 표시
- 알림 탭 시 `/summary/{meetingId}` 라우팅
- 검증: 포그라운드/백그라운드/종료 상태에서 알림 동작 확인

**Phase 3 완료 기준**: 처리 완료 시 Push 알림 수신, 알림 탭으로 회의록 화면 이동

---

## Phase 4: 권한 관리 (REQ-MOBILE-004)

### Task 4.1: 권한 관리 서비스 구현
- `PermissionService` 클래스 구현 (permission_handler 기반)
- 마이크, 알림, 파일 접근 권한 통합 관리
- 권한 거부 시 설명 다이얼로그 표시
- "다시 묻지 않기" 상태에서 설정 앱 이동 안내

### Task 4.2: 녹음 화면 권한 UX 개선
- RecordingScreen 진입 시 proactive 권한 체크
- 권한 미허용 시 녹음 버튼 비활성화 + 안내 메시지
- 검증: 권한 거부/허용/재요청 모든 시나리오 테스트

**Phase 4 완료 기준**: 모든 권한 시나리오에서 적절한 UX 제공

---

## Phase 5: 딥링크 + 배포 준비 (REQ-MOBILE-005, REQ-MOBILE-006)

### Task 5.1: 딥링크 설정
- iOS Universal Links 또는 Custom URL Scheme 설정
- Android App Links 설정
- go_router에 딥링크 라우트 등록
- 검증: `voicetextnote://summary/{id}` URL로 앱 내 네비게이션

### Task 5.2: 앱 스토어 메타데이터 준비
- App Store Connect / Google Play Console 앱 정보 작성
- 스크린샷 준비 (iPhone, iPad, Android Phone)
- 개인정보 처리방침 URL 설정
- ATS 예외 사유 문서화

**Phase 5 완료 기준**: 앱 스토어 제출 준비 완료

---

## 리스크 분석

| 리스크 | 확률 | 영향도 | 대응 전략 |
|--------|------|--------|----------|
| Android 빌드 실패 (의존성 충돌) | 중간 | 높음 | record 패키지 Android 호환성 사전 확인, gradle 버전 맞춤 |
| 백그라운드 녹음 OS Kill | 중간 | 높음 | 주기적 flush + 복구 로직, Foreground Service 유지 |
| APNs 인증서 설정 복잡 | 낮음 | 중간 | .p8 키 기반 인증 사용 (인증서 갱신 불필요) |
| Firebase 초기 설정 오류 | 중간 | 중간 | 공식 FlutterFire CLI 도구 활용 |
| iOS 앱 심사 거절 (ATS 예외) | 낮음 | 높음 | Tailscale 내부망 사유 명시, 필요시 HTTPS 전환 |

---

## 작업 순서 의존성

```
Phase 1 (빌드 기반) ──→ Phase 2 (백그라운드 녹음)
                    ──→ Phase 3 (Push 알림)
                    ──→ Phase 4 (권한 관리)
Phase 2 + 3 + 4 ──────→ Phase 5 (배포 준비)
```

- Phase 2, 3, 4는 Phase 1 완료 후 병렬 진행 가능
- Phase 5는 모든 기능 구현 완료 후 진행

---

## 예상 파일 변경 목록

### 신규 파일

| 파일 | 용도 |
|------|------|
| `client/lib/services/push_notification_service.dart` | FCM 통합, 토큰 관리, 메시지 핸들링 |
| `client/lib/services/permission_service.dart` | 플랫폼 권한 통합 관리 |
| `client/lib/providers/notification_provider.dart` | 알림 상태 관리 (Riverpod) |
| `client/lib/config/firebase_config.dart` | Firebase 초기화 설정 |
| `client/ios/GoogleService-Info.plist` | iOS Firebase 설정 |
| `client/android/app/google-services.json` | Android Firebase 설정 |
| `client/assets/icon/app_icon.png` | 앱 아이콘 소스 이미지 |
| `backend/app/services/push_service.py` | 백엔드 FCM 전송 서비스 |
| `backend/app/api/v1/routes/devices.py` | 디바이스 토큰 등록 API |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `client/pubspec.yaml` | 의존성 추가 (firebase, notifications, permissions 등) |
| `client/lib/main.dart` | Firebase 초기화, 알림 서비스 초기화 |
| `client/ios/Runner/Info.plist` | 백그라운드 모드, Push 설정 추가 |
| `client/lib/providers/recording_provider.dart` | audio_session 통합, 백그라운드 지원 |
| `client/lib/screens/recording_screen.dart` | 권한 UX 개선 |
| `client/lib/config/app_config.dart` | Firebase 관련 설정 추가 |
| `backend/workers/tasks/` | 작업 완료 시 Push 알림 트리거 |
