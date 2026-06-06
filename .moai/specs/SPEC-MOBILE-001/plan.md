# SPEC-MOBILE-001: 실행 계획 (v2.0.0)

## 의존성 그래프

```
Phase A: Backend Infrastructure
  A1 (DB persistence) ──→ A2 (Firebase Admin SDK) ──→ A3 (Celery hooks)
                                                              │
Phase B: iOS Push Config ◄─────────────────────────────────── │
  B1 (Info.plist) ──→ B2 (Entitlements)                       │
                                                              │
Phase C: Deep Links + Navigation                              │
  C1 (iOS scheme) ──┐                                         │
  C2 (Android intent) ├──→ C3 (go_router)                     │
                                                              │
Phase D: App Store Prep                                       │
  (Phase A+B+C 완료 후)                                      │
                                                              │
Phase E: Integration Testing ◄────────────────────────────────┘
  (모든 Phase 완료 후)
```

---

## Phase A: 백엔드 인프라 (REQ-MOBILE-002 수정분)

### A1: DB Persistence — device_tokens 테이블

**목표**: FCM 토큰을 메모리가 아닌 PostgreSQL에 영속 저장하여 서버 재시작 시에도 토큰이 유지된다.

**태스크**:
- `device_tokens` 테이블 DDL 작성 (user_id, fcm_token UNIQUE, platform, is_active, timestamps)
- SQLAlchemy 모델 `DeviceToken` 생성 (`backend/app/models/device_token.py`)
- Alembic 마이그레이션 파일 생성
- `GET /api/v1/devices/{user_id}` 조회 엔드포인트 (관리자용)
- 유닛 테스트: CRUD 동작, UPSERT 동작, 인덱스 성능

**완료 기준**:
- 마이그레이션 실행 후 테이블 생성 확인
- 동일 fcm_token UPSERT 시 갱신(INSERT 아님) 확인
- 서버 재시작 후에도 등록된 토큰 조회 가능

### A2: Firebase Admin SDK 통합

**목표**: `firebase-admin` Python 패키지로 FCM HTTP v1 API를 직접 호출하지 않고 Admin SDK를 통해 Push 알림을 전송한다.

**태스크**:
- `firebase-admin>=6.5.0` 의존성 추가 (requirements.txt / pyproject.toml)
- 서비스 계정 키 환경변수 설정 (`FIREBASE_SERVICE_ACCOUNT_KEY_PATH` 또는 JSON 직접)
- `PushService` 클래스 구현 (`backend/app/services/push_service.py`)
  - `send_to_user(user_id, meeting_id, title, body)` — 사용자 활성 토큰 전체에 전송
  - `send_to_token(fcm_token, meeting_id, title, body)` — 단일 토큰 전송
  - `invalidate_token(fcm_token)` — UNREGISTERED 응답 시 무효화
- `POST /api/v1/devices/register` 엔드포인트 구현 (토큰 UPSERT)
- `DELETE /api/v1/devices/{fcm_token}` 엔드포인트 구현 (토큰 무효화)
- 유닛 테스트: PushService 메서드, 에러 핸들링, 토큰 무효화

**완료 기준**:
- Firebase Admin SDK 초기화 성공 (서비스 계정 키 로드)
- 단일 토큰으로 테스트 Push 전송 성공
- FCM UNREGISTERED 응답 시 자동 무효화 동작

### A3: Celery Push Hooks

**목표**: Celery 작업 완료/실패 시 자동으로 Push 알림을 트리거한다.

**태스크**:
- `on_success` hook 구현: `meeting_id` 포함 payload로 Push 전송
- `on_failure` hook 구현: 에러 정보 포함 Push 전송
- 기존 Celery 태스크에 hook 연결 (`bind=True`, `after_return` 활용)
- 통합 테스트: STT → Diarization → Summary 완료 후 Push 수신

**완료 기준**:
- 파이프라인 정상 완료 시 `on_success` Push 수신 (payload에 `meeting_id` 포함)
- 파이프라인 실패 시 `on_failure` Push 수신
- Push 미전송 시에도 파이프라인 자체는 영향받지 않음 (비동기, 실패 격리)

---

## Phase B: iOS Push Configuration

### B1: Info.plist 설정

**목표**: iOS에서 Push 알림 수신 및 백그라운드 처리를 위한 Info.plist 설정.

**태스크**:
- `UIBackgroundModes`에 `remote-notification` 추가 (기존 `audio` 유지)
- `FirebaseAppDelegateProxyEnabled` → `NO` (수동 메시지 핸들링)
- `NSUserNotificationsUsageDescription` 추가 (필요 시)
- 빌드 검증: `flutter build ios --debug`

**완료 기준**:
- iOS 빌드 성공
- Info.plist에 `remote-notification` 백그라운드 모드 포함 확인

### B2: Entitlements 설정

**목표**: iOS Push Notification capability 및 APNs 환경 설정.

**태스크**:
- `Runner.entitlements`에 `aps-environment: development` 추가 (개발 환경)
- Xcode 프로젝트에 Push Notification capability 활성화
- Background Modes capability에서 Remote notifications 체크
- 빌드 검증: 실기기에서 Push 수신 테스트

**완료 기준**:
- `.entitlements` 파일에 `aps-environment` 설정 확인
- Xcode Capability에 Push Notification 표시 확인

---

## Phase C: Deep Links + Navigation (REQ-MOBILE-006 수정분)

### C1: iOS URL Scheme

**목표**: iOS에서 `voicetextnote://` Custom URL Scheme을 처리한다.

**태스크**:
- Info.plist `CFBundleURLTypes` → `CFBundleURLSchemes: [voicetextnote]` 등록
- `DeepLinkService` 클래스 구현 (`client/lib/services/deep_link_service.dart`)
  - URL 파싱: `voicetextnote://summary/{id}` → `/summary/{id}` 변환
  - 에러 처리: 유효하지 않은 URL → 에러 화면 fallback
- 검증: Safari에서 `voicetextnote://summary/test123` 열기 → 앱 내 네비게이션

**완료 기준**:
- 외부 URL로 앱이 열리고 올바른 화면으로 이동
- 잘못된 URL에 대해 에러 화면 표시

### C2: Android Intent Filter

**목표**: Android에서 `voicetextnote://` scheme Intent Filter를 처리한다.

**태스크**:
- `AndroidManifest.xml`에 `<intent-filter>` 추가
  - `<data android:scheme="voicetextnote" />`
  - `<action android:name="android.intent.action.VIEW" />`
  - `<category android:name="android.intent.category.DEFAULT" />`
  - `<category android:name="android.intent.category.BROWSABLE" />`
- 검증: `adb shell am start -a android.intent.action.VIEW -d "voicetextnote://summary/test123"` → 앱 내 네비게이션

**완료 기준**:
- ADB 명령으로 딥링크 열기 → 올바른 화면 이동
- 브라우저에서 URL 클릭 시 앱 열기 확인

### C3: go_router 통합

**목표**: go_router를 통해 모든 딥링크(Cold start, Background, Foreground)를 처리한다.

**태스크**:
- `GoRouter`에 `initialUri` 처리 로직 추가
- Firebase `getInitialMessage()` → cold start 딥링크 처리
- Firebase `onMessageOpenedApp` → background 딥링크 처리
- `flutter_local_notifications` `onDidReceiveNotificationResponse` → foreground 딥링크 처리
- `DeepLinkService`에서 URL → Route 매핑 통합 관리
- 검증: 3가지 시나리오(cold/background/foreground) 모두에서 딥링크 동작

**완료 기준**:
- Cold start: 앱 종료 상태 → Push 탭 → 정확한 화면 표시
- Background: 앱 백그라운드 → Push 탭 → 정확한 화면 표시
- Foreground: 앱 사용 중 → Push 수신 → 배너 표시 → 탭 → 화면 이동

---

## Phase D: App Store Preparation (REQ-MOBILE-005)

### D1: 메타데이터 및 스크린샷

**목표**: 앱 스토어 제출을 위한 메타데이터와 스크린샷을 준비한다.

**태스크**:
- App Store Connect 앱 정보 등록 (이름, 설명, 카테고리, 키워드)
- Google Play Console 앱 정보 등록
- iOS/Android 스크린샷 캡처 (각 디바이스 사이즈별)
- Privacy Policy URL 설정
- ATS 예외 사유 문서화 (Tailscale HTTP 접속)

**완료 기준**:
- App Store Connect / Google Play Console 메타데이터 입력 완료
- 스크린샷 준비 완료

---

## Phase E: Integration Testing

### E1: E2E Push 알림 테스트

**목표**: 녹음 → 업로드 → 처리 → Push 수신 → 딥링크 전체 플로우를 검증한다.

**태스크**:
- 실기기(iOS/Android)에서 녹음 → 업로드 → 처리 완료 → Push 수신 (5분 이내)
- Cold start: 앱 종료 → Push 탭 → 회의록 화면
- Background: 앱 백그라운드 → Push 탭 → 회의록 화면
- Foreground: 앱 사용 중 → Push 배너 → 탭 → 회의록 화면
- 잘못된 meetingId → 에러 화면 fallback

**완료 기준**:
- 모든 Push 시나리오에서 올바른 네비게이션 동작
- payload에 `meeting_id` 포함 확인

### E2: 백그라운드 녹음 테스트

**목표**: iOS/Android에서 백그라운드 녹음 지속성을 검증한다.

**태스크**:
- iOS: 녹음 시작 → 홈 화면 → 30초 대기 → 복귀 → 경과 시간 확인
- Android: 녹음 시작 → 홈 화면 → 상태바 Notification 확인 → 복귀 → 경과 시간 확인
- 백그라운드 녹음 후 업로드 → STT 결과에 백그라운드 구간 음성 포함 확인
- 강제 종료 → 재시작 → 미완료 파일 감지 확인

**완료 기준**:
- iOS/Android 모두 백그라운드에서 녹음 지속 (최소 30분)
- 강제 종료 후 파일 보존 확인

### E3: 딥링크 E2E 테스트

**목표**: 모든 딥링크 진입 경로를 검증한다.

**태스크**:
- Push 알림 탭 (cold start / background / foreground)
- URL Scheme 직접 호출 (iOS Safari / Android ADB)
- 유효하지 않은 meetingId → 에러 화면

**완료 기준**:
- 3가지 진입 경로 모두 올바른 화면 이동
- 에러 케이스에서 crash 없이 fallback

---

## 리스크 분석

| 리스크 | 확률 | 영향도 | 대응 전략 |
|--------|------|--------|----------|
| Firebase 프로젝트 설정 오류 | 중간 | 높음 | FlutterFire CLI 사용, 공식 가이드 준수 |
| Firebase Admin SDK 인증 실패 | 낮음 | 높음 | 서비스 계정 키 JSON 검증, 환경변수 확인 스크립트 |
| Android 빌드 실패 (의존성 충돌) | 중간 | 높음 | record 패키지 Android 호환성 사전 확인, gradle 버전 맞춤 |
| Celery hook이 파이프라인에 영향 | 낮음 | 높음 | Push 전송을 비동기/별도 태스크로 격리, 실패 시 로깅만 |
| 백그라운드 녹음 OS Kill | 중간 | 높음 | 10초 이하 flush + 복구 로직, Foreground Service 유지 |
| Cold start 딥링크 라우팅 실패 | 중간 | 중간 | go_router 초기화 순서 보장, DeepLinkService 큐잉 |
| iOS 앱 심사 거절 (ATS 예외) | 낮음 | 높음 | Tailscale 내부망 사유 명시, 필요시 HTTPS 전환 |
| FCM 토큰 만료 미감지 | 낮음 | 중간 | Admin SDK UNREGISTERED 응답 시 자동 무효화 로직 |

---

## 파일 변경 목록

### 신규 파일

| 파일 | 용도 | Phase |
|------|------|-------|
| `backend/app/models/device_token.py` | SQLAlchemy DeviceToken 모델 | A1 |
| `backend/alembic/versions/xxx_add_device_tokens.py` | device_tokens 마이그레이션 | A1 |
| `backend/app/services/push_service.py` | Firebase Admin SDK Push 전송 서비스 | A2 |
| `backend/app/api/v1/routes/devices.py` | 디바이스 토큰 등록/조회/삭제 API | A2 |
| `backend/app/workers/hooks/celery_push_hooks.py` | Celery on_success/on_failure Push hook | A3 |
| `client/lib/services/deep_link_service.dart` | 딥링크 파싱, 콜드스타트/백그라운드 처리 | C3 |
| `client/lib/services/push_notification_service.dart` | FCM 통합, 토큰 관리, 메시지 핸들링 | B1 |
| `client/lib/services/permission_service.dart` | 플랫폼 권한 통합 관리 | B1 |
| `client/lib/providers/notification_provider.dart` | 알림 상태 관리 (Riverpod) | B1 |
| `client/lib/config/firebase_config.dart` | Firebase 초기화 설정 | B1 |
| `client/ios/GoogleService-Info.plist` | iOS Firebase 설정 | B1 |
| `client/ios/Runner/Runner.entitlements` | Push Notification entitlement | B2 |
| `client/android/app/google-services.json` | Android Firebase 설정 | B1 |
| `client/assets/icon/app_icon.png` | 앱 아이콘 소스 이미지 | D1 |

### 수정 파일

| 파일 | 변경 내용 | Phase |
|------|----------|-------|
| `client/pubspec.yaml` | 의존성 추가 (firebase, notifications, permissions 등) | B1 |
| `client/lib/main.dart` | Firebase 초기화, 알림 서비스 초기화, 딥링크 초기화 | B1, C3 |
| `client/ios/Runner/Info.plist` | 백그라운드 모드(remote-notification), URL Scheme, Push 설정 | B1, C1 |
| `client/android/app/src/main/AndroidManifest.xml` | Foreground Service, intent-filter, 권한 | C2 |
| `client/lib/providers/recording_provider.dart` | audio_session 통합, 백그라운드 지원, flush 간격 조정 | E2 |
| `client/lib/screens/recording_screen.dart` | 권한 UX 개선 | B1 |
| `client/lib/config/app_config.dart` | Firebase 관련 설정 추가 | B1 |
| `backend/requirements.txt` 또는 `pyproject.toml` | `firebase-admin>=6.5.0` 추가 | A2 |
| `backend/app/workers/tasks/` | 기존 Celery 태스크에 Push hook 연결 | A3 |

---

## 제약사항

1. **Firebase 선작업 필수**: Phase A2, B, C 모두 Firebase 프로젝트 생성이 선행되어야 한다.
2. **실기기 테스트 필수**: Push 알림은 시뮬레이터에서 제한적이므로 Phase E는 실기기에서 수행해야 한다.
3. **서비스 계정 키 관리**: `serviceAccountKey.json`은 절대 Git에 커밋하지 않고 환경변수로만 참조한다.
4. **Push 전송 실패 격리**: Celery hook에서 Push 전송 실패가 파이프라인 완료 자체에 영향을 주지 않아야 한다.
5. **iOS 배포는 Apple Developer 계정 필요**: Phase D는 Apple Developer Program 가입이 전제조건이다.
