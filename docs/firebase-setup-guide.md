# Firebase 설정 절차 문서 (T-019)

**SPEC-MOBILE-004 | 작성일: 2026-06-13**

---

## 1. Firebase 프로젝트 생성

1. [Firebase Console](https://console.firebase.google.com/) 접속
2. "프로젝트 추가" → 프로젝트명: `voice-to-textnote`
3. Google Analytics 비활성화 (로컬 전용 앱)

## 2. Android 앱 등록

1. 패키지명: `com.voicetextnote.app`
2. SHA-1 인증서 지문 등록:
   ```bash
   cd client/android
   ./gradlew signingReport
   ```
3. `google-services.json` 다운로드 → `client/android/app/` 에 배치

## 3. iOS 앱 등록

1. Bundle ID: `com.voicetextnote.app`
2. `GoogleService-Info.plist` 다운로드 → `client/ios/Runner/` 에 배치
3. APNs 인증 키(.p8) 생성:
   - Apple Developer → Keys → "Firebase Auth Key" 생성
   - Key ID, Team ID 기록
   - Firebase Console → 프로젝트 설정 → Cloud Messaging → APNs 인증 키 업로드

## 4. 백엔드 서비스 계정 키

1. Firebase Console → 프로젝트 설정 → 서비스 계정
2. "새 비공개 키 생성" → JSON 파일 다운로드
3. 서버 환경에 배치:
   ```bash
   # .env.local 또는 환경 변수
   FIREBASE_CREDENTIALS_PATH=/path/to/service-account-key.json
   ```
4. `config.py`에서 `firebase_credentials_path` 설정 확인

## 5. FCM 설정 확인

### 클라이언트 (Flutter)
- `firebase_messaging` 패키지 자동 초기화
- 백그라운드 핸들러: `registerFCMBackgroundHandler()` (main.dart)
- 딥링크: `voicetextnote://meeting/{id}` 스킴 처리

### 백엔드 (Python)
- `push_service.py`: `firebase_admin` 초기화 (MOCK 폴백 지원)
- `celery_push_hooks.py`: Celery 태스크 완료 시 FCM 전송
- MOCK 모드: `FIREBASE_CREDENTIALS_PATH` 미설정 시 자동 활성화

## 6. 디버그 / 검증

```bash
# 저장소/CI에서 항상 실행 가능한 정적 release readiness 검사
python3 client/scripts/verify_release_readiness.py

# 실제 서비스 계정/APNs/App Store Connect/실기기 정보까지 요구하는 운영 전 검사
FIREBASE_CREDENTIALS_PATH=/secure/service-account.json \
APNS_AUTH_KEY_PATH=/secure/AuthKey_XXXXXXXXXX.p8 \
APNS_KEY_ID=XXXXXXXXXX \
APNS_TEAM_ID=XXXXXXXXXX \
APP_STORE_CONNECT_API_KEY_PATH=/secure/AuthKey_YYYYYYYYYY.p8 \
APP_STORE_CONNECT_KEY_ID=YYYYYYYYYY \
APP_STORE_CONNECT_ISSUER_ID=<issuer-uuid> \
ANDROID_DEVICE_SERIAL=<adb-device-serial> \
IOS_DEVICE_UDID=<ios-device-udid> \
FIREBASE_TEST_DEVICE_TOKEN=<fcm-token> \
python3 client/scripts/verify_release_readiness.py --strict

# 클라이언트 FCM 토큰 확인 (앱 실행 후 로그)
flutter run -d <device> --verbose

# 백엔드 FCM 전송 테스트 (MOCK 모드)
python -c "from backend.services.push_service import PushService; svc = PushService(); print(svc._is_mock_mode)"

# 실제 전송 테스트
curl -X POST http://localhost:8000/api/v1/devices/register \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"fcm_token": "<DEVICE_TOKEN>"}'
```

## 7. 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| FCM 토큰 수신 안됨 | `google-services.json` 미배치 | 파일 경로 확인 |
| 백엔드 전송 실패 | 서비스 계정 키 미설정 | `FIREBASE_CREDENTIALS_PATH` 확인 |
| iOS APNs 미수신 | APNs 키 미업로드 | .p8 키 Firebase 콘솔 등록 |
| 백그라운드 핸들러 미작동 | `FirebaseAppDelegateProxyEnabled: false` 확인 | Info.plist 확인 (정상) |
