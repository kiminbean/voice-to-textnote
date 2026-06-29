# Google Sign-In / Firebase iOS Runbook

작성일: 2026-06-27

이 문서는 `voice-to-textnote` Firebase/Google 로그인 작업 중 발생한 실패와 해결책을 재발 방지용으로 정리한 운영 메모다.

## 현재 기준값

- Firebase project: `voice-to-textnote`
- Firebase CLI: 설치됨, 로그인 계정 `kiminbean@gmail.com`
- iOS bundle ID: `com.voicetextnote.app`
- macOS bundle ID: `com.voicetextnote.voiceToTextnote`
- Android package: `com.voicetextnote.app`
- iPhone device ID: `00008150-000239020C08401C`
- iPhone CoreDevice ID: `C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA`
- Local backend for iPhone profile build: `http://100.69.69.119:8000/api/v1`
- Remote backend PC: Tailscale `100.69.69.119`, repo `/Users/ibkim/Projects/voice-to-textnote`
- Last verified APNs/FCM commit: `25dce3d`

## Firebase 파일 위치

Firebase 설정 파일은 아래 위치에 있어야 한다.

```text
client/android/app/google-services.json
client/ios/Runner/GoogleService-Info.plist
client/macos/Runner/GoogleService-Info.plist
client/.firebaserc
```

`client/.firebaserc`는 기본 프로젝트가 `voice-to-textnote`여야 한다.

## Google OAuth client ID 규칙

백엔드 `.env`의 `GOOGLE_CLIENT_ID`는 Web client ID 하나만 두면 iOS 토큰 검증에서 실패할 수 있다. 반드시 Web, Android, iOS, macOS OAuth client ID를 쉼표로 모두 허용한다.

```env
GOOGLE_CLIENT_ID=<WEB_CLIENT_ID>,<ANDROID_CLIENT_ID>,<IOS_CLIENT_ID>,<MACOS_CLIENT_ID>
```

이 값은 토큰 원문이나 secret이 아니라 OAuth audience 허용 목록이다. 그래도 불필요하게 채팅이나 로그에 전체 값을 노출하지 않는다.

## iOS Info.plist 필수 항목

`client/ios/Runner/Info.plist`에는 아래 항목이 필요하다.

- `GIDClientID`: iOS `GoogleService-Info.plist`의 `CLIENT_ID`
- `GIDServerClientID`: Web OAuth client ID
- `CFBundleURLTypes`: iOS `GoogleService-Info.plist`의 `REVERSED_CLIENT_ID`
- `NSLocalNetworkUsageDescription`: 실기기에서 로컬 백엔드 접근 시 필요
- ATS local HTTP 예외: 개발용 `localhost`, Tailscale/LAN IP 접근 허용

macOS도 `client/macos/Runner/Info.plist`에 macOS client ID와 Web server client ID를 둔다.

## 앱 실행 규칙

iOS 14+에서 Flutter debug 빌드는 홈 화면에서 직접 실행하면 종료된다.

대표 로그:

```text
Cannot create a FlutterEngine instance in debug mode without Flutter tooling or Xcode.
```

홈 화면에서 직접 실행해 테스트할 때는 debug 빌드가 아니라 profile 빌드를 설치한다.

```bash
cd client
flutter run --profile \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=dev \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

실기기에 최종 확인용으로 올릴 때는 release 빌드를 사용한다.

```bash
cd client
flutter run --release --no-pub --no-resident \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=dev \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

`flutter run --profile`이 VM service 연결 문제로 종료되더라도 앱 설치 자체가 완료되고 profile 앱 프로세스가 살아 있으면 홈 화면 실행은 가능하다.

프로세스 확인:

```bash
xcrun devicectl device info processes \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA | rg -i 'Runner|voicetext'
```

앱 직접 실행:

```bash
xcrun devicectl device process launch \
  --device C7DD57C9-48FC-5362-B2FB-ED87CFFD51FA \
  --terminate-existing \
  com.voicetextnote.app
```

## APNs / FCM 실기기 Push 규칙

2026-06-30 기준 iPhone 실기기 개발 Push는 실제 FCM/APNs 전송까지 검증되었다.

확인된 상태:

- Xcode signing은 Automatic이다.
- `client/ios/Runner.xcodeproj/project.pbxproj`가 `Runner/Runner.entitlements`를 사용한다.
- `AppDelegate.swift`가 APNs registration을 호출하고, `didRegisterForRemoteNotificationsWithDeviceToken`에서 `Messaging.messaging().apnsToken`을 설정한다.
- Flutter `PushNotificationService`는 iOS/macOS에서 FCM token 요청 전에 APNs token을 짧게 기다린다.
- 앱은 백엔드 `/devices/register`에 `platform=ios`로 device token을 등록한다.
- 실제 iPhone에서 `APNs 토큰 준비 완료`, `토픽 구독 완료: all`, `/api/v1/devices/register` 201이 확인되었다.

프로필 빌드로 iPhone에 설치할 때:

```bash
cd client
flutter run --profile --no-pub \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

원격 백엔드 PC의 Firebase Admin 설정:

```text
FIREBASE_CREDENTIALS_PATH=/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json
```

주의:

- 서비스 계정 JSON은 repo 밖에 두고 git에 커밋하지 않는다.
- 원격 `.env`에 `FIREBASE_PROJECT_ID`를 추가하지 않는다. 현재 Settings 모델이 허용하지 않아 서버가 시작 실패한다.
- 로컬 `.env`를 원격으로 동기화할 때 원격의 `FIREBASE_CREDENTIALS_PATH`를 보존한다.

실제 모드 확인:

```bash
ssh 100.69.69.119 'cd /Users/ibkim/Projects/voice-to-textnote && .venv/bin/python - <<'"'"'PY'"'"'
from backend.services.push_service import PushService

svc = PushService()
svc._ensure_firebase_initialized()
print("mock_mode", svc._is_mock_mode)
PY'
```

기대값:

```text
mock_mode False
```

실제 전송 검증은 Firebase Admin SDK의 `messaging.send(...)`가 message id를 반환하면 성공으로 본다. 2026-06-30 검증 message id:

```text
projects/voice-to-textnote/messages/1782749586143713
```

iOS 앱이 포그라운드 상태이면 시스템 배너가 보이지 않을 수 있다. 배너 표시까지 확인하려면 앱을 백그라운드로 보내거나 화면을 잠근 상태에서 전송한다. 서버 측 성공 여부는 Firebase message id와 예외 없는 `send_ok True`를 기준으로 판단한다.

## 로컬 서버 실행 규칙

Google 로그인 테스트 전에 Redis와 백엔드가 떠 있어야 한다.

```bash
tmux new-session -d -s voice-to-textnote-redis \
  '/opt/homebrew/bin/redis-server --port 6379 --save "" --appendonly no'

tmux new-session -d -s voice-to-textnote-server \
  -c /Users/ibkim/Projects/voice-to-textnote \
  'PYTEST_CURRENT_TEST=server_startup HUGGINGFACE_TOKEN= python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 2>&1 | tee -a logs/backend.log'
```

`PYTEST_CURRENT_TEST=server_startup`는 로컬 로그인 검증 중 STT 모델 프리로드를 건너뛰기 위한 개발용 설정이다. 로그인 검증에는 필요 없는 모델 로딩 실패로 서버가 죽지 않게 한다.

검증:

```bash
/opt/homebrew/bin/redis-cli ping
curl -sS -o /tmp/vtt_guest.out -w 'guest:%{http_code}\n' -X POST http://100.69.69.119:8000/api/v1/auth/guest
curl -sS -o /tmp/vtt_openapi.out -w 'openapi:%{http_code}\n' http://100.69.69.119:8000/openapi.json
```

기대값:

```text
PONG
guest:200
openapi:200
```

## 실패 원인과 해결 기록

| 증상 | 실제 원인 | 해결 |
| --- | --- | --- |
| Google 계정 선택 후 "이메일 또는 비밀번호가 올바르지 않습니다" | Google login 401을 이메일 로그인 오류 문구로 잘못 매핑 | 소셜 로그인 오류 메시지를 별도 처리 |
| 서버 로그 `Invalid audience` | 백엔드가 Web OAuth client ID 하나만 허용하거나 audience 검증 경로가 불명확 | `GOOGLE_CLIENT_ID`를 쉼표 구분 다중 audience로 설정하고 서버에서 `aud` 직접 검증 |
| 서버 로그 `No access_token provided to compare against at_hash claim` | `python-jose`가 ID token의 `at_hash`를 access token 없이 자동 검증 | `jwt.decode(..., options={"verify_aud": False, "verify_at_hash": False})`, 이후 issuer/audience 직접 검증 |
| 앱 아이콘 실행 시 바로 종료 | Flutter debug 빌드를 홈 화면에서 직접 실행 | iPhone에는 profile 빌드 설치 |
| `/auth/guest` 500 | Redis 미기동 | `voice-to-textnote-redis` tmux 세션으로 Redis 실행 |
| `/openapi.json` 500 | `pydantic` 파일/메타데이터 버전 불일치 | 서버 Python에서 `pydantic[email]>=2.9` 재설치 |
| 앱에서 로컬 API 접근 실패 가능 | iPhone의 `localhost`는 Mac이 아니며, iOS Local Network/ATS 설정 필요 | `API_BASE_URL`을 Mac LAN/Tailscale IP로 지정하고 `Info.plist`에 local network/ATS 예외 추가 |
| `/api/v1/history` 401 `API Key 누락` | API key 보호 라우트 호출 | Google 로그인 실패와 별개. 로그인 디버깅 시 `/auth/google` 로그를 기준으로 판단 |
| 녹음 후 `STT 처리중 20%`에서 멈춤 | 20%는 업로드 성공 후 STT/DIA 완료를 기다리는 지점이다. 클라이언트 SSE가 `Authorization`/guest 토큰 없이 연결했고, 병렬 STT/DIA 대기 중 하나의 SSE HTTP client를 공유했으며, 이벤트가 없을 때 폴링 fallback이 늦었다. | commit `537a0ac`처럼 SSE에 API key 또는 bearer/guest 인증 헤더를 넣고, 연결별 HTTP client를 사용하며, idle timeout 후 status polling으로 전환한다. |
| iOS 빌드가 `FlutterEngine.h has been modified since the precompiled header`로 실패 | Xcode/Flutter precompiled header cache 불일치 | `flutter clean && flutter pub get --offline` 후 다시 빌드한다. 이 과정에서 `pubspec.lock`, `Podfile.lock`, generated registrant, SwiftPM `Package.resolved`가 흔들릴 수 있으므로 커밋 전 관련 없는 diff를 되돌린다. |
| FCM token이 늦게 나오거나 backend device registration이 누락됨 | iOS APNs token이 Firebase Messaging에 연결되기 전에 FCM token을 요청했거나 auth restore 전에 notification 초기화를 시작함 | `AppDelegate.swift`의 APNs token bridge, `PushNotificationService._waitForApnsToken()`, auth state 전환 후 notification 초기화 흐름을 유지한다. |
| 백엔드 PushService가 MOCK 모드 | 원격 `.env`에 `FIREBASE_CREDENTIALS_PATH`가 없거나 서비스 계정 JSON 경로/권한이 잘못됨 | 원격 파일 `/Users/ibkim/secure/voice-to-textnote/firebase-adminsdk-fbsvc.json`과 `.env` 키를 확인하고 백엔드를 재시작한다. |
| 백엔드가 `firebase_project_id extra_forbidden`으로 시작 실패 | `.env`에 현재 Settings 모델이 허용하지 않는 `FIREBASE_PROJECT_ID`가 들어감 | 원격 `.env`에서 `FIREBASE_PROJECT_ID`를 제거하고 재시작한다. |

## STT 20% 멈춤 진단 규칙

앱 진행률 20%는 `PipelineStep.transcribing` 진입 직후다. 즉 파일 업로드는 성공했고, 앱이 STT task와 diarization task 완료를 기다리는 상태다.

점검 순서:

1. 앱이 최신 빌드인지 확인한다. `537a0ac` 이후 빌드여야 한다.
2. 서버가 살아 있는지 확인한다.

```bash
curl -sS -o /tmp/vtt_health.out -w 'health:%{http_code}\n' http://100.69.69.119:8000/health
curl -sS -o /tmp/vtt_openapi.out -w 'openapi:%{http_code}\n' http://100.69.69.119:8000/openapi.json
curl -sS -o /tmp/vtt_guest.out -w 'guest:%{http_code}\n' -X POST http://100.69.69.119:8000/api/v1/auth/guest
```

기대값은 모두 `200`이다.

3. 실제 짧은 WAV를 업로드해 STT와 DIA task가 `completed`까지 가는지 확인한다.
4. SSE는 인증이 필요하다. guest 앱 경로에서는 `Authorization: Bearer guest:<guest_token>` 헤더가 있어야 `GET /api/v1/tasks/{task_id}/stream`이 `200 text/event-stream`을 반환한다.
5. 서버 처리 자체가 완료되는데 앱만 멈추면 `client/lib/services/sse_service.dart`와 `client/lib/providers/pipeline_provider.dart`의 인증 헤더, 연결별 client, polling fallback을 먼저 본다.

관련 파일:

- `client/lib/services/sse_service.dart`
- `client/lib/providers/pipeline_provider.dart`
- `client/lib/screens/processing_screen.dart`
- `client/test/services/sse_service_test.dart`

관련 검증:

```bash
cd client
flutter test --no-pub test/services/sse_service_test.dart test/providers/pipeline_provider_test.dart
flutter analyze --no-pub
```

## Google token 검증 원칙

백엔드는 Google ID token에 대해 다음을 검증한다.

- Google 공개키 `kid` 매칭
- JWT 서명
- 만료
- issuer: `https://accounts.google.com` 또는 `accounts.google.com`
- audience: `.env` `GOOGLE_CLIENT_ID` 목록 중 하나
- 필수 claim: `sub`, `email`

토큰 원문은 로그에 남기지 않는다. audience mismatch 진단이 필요하면 `aud`, `azp`, 허용 audience suffix/count만 로그에 남긴다.

## 반복 방지 체크리스트

Google 로그인이 실패하면 순서대로 본다.

1. 앱이 debug 빌드인지 profile 빌드인지 확인한다.
2. `voice-to-textnote-server`, `voice-to-textnote-redis` tmux 세션이 살아 있는지 확인한다.
3. `curl`로 `guest:200`, `openapi:200`을 확인한다.
4. 서버 로그에서 `/api/v1/auth/google` 401 사유를 확인한다.
5. `Invalid audience`면 `.env GOOGLE_CLIENT_ID` 목록과 token `aud`를 비교한다.
6. `at_hash` 오류면 `verify_at_hash`가 꺼져 있는지 확인한다.
7. 앱 표시 문구만 보지 말고 반드시 서버 로그의 `/auth/google` 원인을 기준으로 판단한다.

## 검증 명령

```bash
pytest backend/tests/unit/test_oauth_service.py -q --no-cov

cd client
flutter analyze
flutter test test/providers/auth_provider_google_test.dart test/config/ios_permission_config_test.dart
```

`flutter test`/`flutter run`이 `pubspec.lock`, `Podfile.lock`, generated registrant, SwiftPM `Package.resolved`를 자동 변경할 수 있다. 로그인 수정과 무관한 생성물 변경은 커밋 전에 diff를 확인하고 정리한다.
