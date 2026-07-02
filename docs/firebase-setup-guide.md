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

### Android Google 로그인 SHA-1 기준값

USB 실기기 릴리스 APK 검증 중 Google Play Services가 아래 오류를 반환했다.

```text
This android application is not registered to use OAuth2.0,
please confirm the package name and SHA-1 certificate fingerprint match
what you registered in Google Developer Console.
```

현재 Android OAuth client에는 package `com.voicetextnote.app`에 대해 아래 SHA-1 조합이 등록되어 있어야 한다.

```text
Debug/local profile SHA-1:
SHA-1: 1F:84:A6:04:D6:18:F5:17:EE:AC:5D:6D:5A:D5:EE:62:B0:C0:FC:66
SHA-256: 22:9C:9D:7D:E9:8F:17:9C:AC:D4:65:E3:E9:FD:BA:D4:59:01:9C:BF:7C:21:F0:37:BF:0C:C5:04:D4:71:0D:1B

Mac mini release upload key SHA-1 (2026-07-02):
SHA-1: 45:6F:94:A6:F0:78:99:7A:8D:E9:DB:9C:C2:F1:03:B7:FF:BE:B7:4C
SHA-256: BE:E7:20:D7:CD:3B:0C:A2:B0:AF:5B:CE:5E:D0:0C:50:55:3E:79:EC:FB:62:80:7D:4A:67:63:3B:9B:33:A7:55
```

Google Cloud Console / Firebase Console의 Android OAuth client에 위 package/SHA-1 조합이 실제로 등록되어 있어야 한다. `google-services.json`에 과거 client entry가 남아 있어도 Cloud Console에서 해당 Android OAuth client가 삭제되었거나 비활성화되면 실기기 로그인은 계속 실패한다.

2026-07-02 Android release 로그인 실패의 직접 원인은 새 upload key SHA-1이 Firebase에 등록되지 않은 상태에서 release APK를 설치한 것이었다. `firebase apps:android:sha:create`로 `45:6F:...:4C`를 등록하고 `firebase apps:sdkconfig ANDROID ...`로 `client/android/app/google-services.json`을 갱신한 뒤 release APK를 재설치했다.

주의:

- Android `serverClientId`는 반드시 Web OAuth client ID여야 한다.
- Android OAuth client ID를 `serverClientId`로 넣는 우회는 실패한다. 2026-06-30 실험에서 Google Play Services가 `You must use a Web client as the server client ID`를 반환했다.
- 실제 Play/App Store 배포용 release key를 사용할 때는 debug SHA-1이 아니라 production/upload signing SHA-1을 별도로 등록한다.

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

### 현재 개발 백엔드 기준값

2026-06-30 기준 원격 개발 백엔드 PC는 Tailscale `100.69.69.119`이며, 저장소 경로는 `/Users/ibkim/Projects/voice-to-textnote`다.

서비스 계정 JSON은 저장소 밖에 둔다.

```text
/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

원격 `.env`에는 아래 키가 필요하다.

```env
FIREBASE_CREDENTIALS_PATH=/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

주의:

- `FIREBASE_PROJECT_ID`는 현재 `Settings` 모델에 없는 키이므로 원격 `.env`에 추가하지 않는다. 추가하면 백엔드 기동이 `extra_forbidden` 검증 오류로 실패한다.
- 로컬 `.env`를 원격 백엔드 PC에 동기화할 때는 원격에만 있는 `FIREBASE_CREDENTIALS_PATH`를 보존한다.
- 서비스 계정 JSON은 로그, 채팅, 문서, git diff에 출력하지 않는다.
- 파일 권한은 `600`을 권장한다.

백엔드 재시작 후 실제 모드 확인:

```bash
cd /Users/ibkim/Projects/voice-to-textnote
.venv/bin/python - <<'PY'
from backend.services.push_service import PushService

svc = PushService()
svc._ensure_firebase_initialized()
print("mock_mode", svc._is_mock_mode)
PY
```

기대값:

```text
mock_mode False
```

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

# iOS 기기가 등록한 최신 FCM token으로 실제 전송 테스트
TOKEN=$(sqlite3 voice_to_textnote.db \
  "select fcm_token from device_tokens where platform='ios' and is_active=1 order by updated_at desc limit 1;")
TOKEN="$TOKEN" .venv/bin/python - <<'PY'
import os
from firebase_admin import messaging
from backend.services.push_service import PushService

svc = PushService()
svc._ensure_firebase_initialized()
message_id = messaging.send(messaging.Message(
    notification=messaging.Notification(
        title="Voice to TextNote 테스트",
        body="실제 FCM/APNs 푸시 전송 확인",
    ),
    data={"source": "manual-fcm-test"},
    token=os.environ["TOKEN"],
))
print("mock_mode", svc._is_mock_mode)
print("message_id", message_id)
PY
```

2026-06-30 실기기 검증에서 Firebase가 반환한 실제 message id:

```text
projects/voice-to-textnote/messages/1782749586143713
```

## 7. 문제 해결

| 증상 | 원인 | 해결 |
|------|------|------|
| FCM 토큰 수신 안됨 | `google-services.json` 미배치 | 파일 경로 확인 |
| 백엔드 전송 실패 | 서비스 계정 키 미설정 | `FIREBASE_CREDENTIALS_PATH` 확인 |
| iOS APNs 미수신 | APNs 키 미업로드 | .p8 키 Firebase 콘솔 등록 |
| 백그라운드 핸들러 미작동 | `FirebaseAppDelegateProxyEnabled: false` 확인 | Info.plist 확인 (정상) |
| Android Google 로그인 직후 일반 오류 또는 `ApiException: 10` | Android OAuth package/SHA-1 조합 미등록 또는 Cloud Console client 삭제 | 실제 설치 APK SHA-1을 `apksigner verify --print-certs`로 확인 후 Firebase/Google Cloud Console에 등록하고 `google-services.json`을 다시 내려받아 release APK를 재설치 |
| `You must use a Web client as the server client ID` | Android OAuth client ID를 `serverClientId`로 전달 | Web OAuth client ID를 사용하거나 `google-services.json`의 `default_web_client_id`를 사용 |

## 8. Google Sign-In / OAuth 주의사항

자세한 재발 방지 runbook은 `docs/google-auth-ios-runbook.md`를 기준으로 한다.

### 필수 설정

- `client/android/app/google-services.json`: Android, Web, iOS OAuth client ID 포함 여부 확인
- `client/ios/Runner/GoogleService-Info.plist`: `CLIENT_ID`, `REVERSED_CLIENT_ID` 포함
- `client/macos/Runner/GoogleService-Info.plist`: macOS용 `CLIENT_ID`, `REVERSED_CLIENT_ID` 포함
- `client/ios/Runner/Info.plist`: `GIDClientID`, `GIDServerClientID`, Google callback URL scheme 포함
- `client/macos/Runner/Info.plist`: `GIDClientID`, `GIDServerClientID`, Google callback URL scheme 포함
- 백엔드 `.env`: `GOOGLE_CLIENT_ID`에 Web/iOS/Android/macOS OAuth client ID를 쉼표 구분으로 모두 설정

### 서버 검증 원칙

Google ID token 검증은 서명, 만료, issuer, audience, `sub`, `email`을 확인한다. `python-jose`의 `at_hash` 자동 검증은 access token 없이 실패할 수 있으므로 서버에서는 `verify_at_hash`를 끄고 필요한 claim을 명시적으로 검증한다.

### 실기기 실행 주의

iOS 14+에서 Flutter debug 빌드를 홈 화면에서 직접 실행하면 다음 오류로 종료된다.

```text
Cannot create a FlutterEngine instance in debug mode without Flutter tooling or Xcode.
```

홈 화면에서 테스트하려면 profile 빌드를 설치한다.

```bash
cd client
flutter run --profile \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

### Google 로그인 실패 진단 순서

1. Redis와 백엔드가 실행 중인지 확인한다.
2. `curl`로 `/api/v1/auth/guest`, `/openapi.json`이 200인지 확인한다.
3. 앱 메시지가 아니라 백엔드 `/api/v1/auth/google` 로그를 본다.
4. `Invalid audience`면 `GOOGLE_CLIENT_ID` 목록과 token audience를 비교한다.
5. `No access_token provided to compare against at_hash claim`이면 `verify_at_hash` 비활성화 여부를 확인한다.
6. `API Key 누락`으로 `/history`가 401인 로그는 Google 로그인 실패와 별개다.
