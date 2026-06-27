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

## 로컬 서버 실행 규칙

Google 로그인 테스트 전에 Redis와 백엔드가 떠 있어야 한다.

```bash
tmux new-session -d -s voice-to-textnote-redis \
  '/opt/homebrew/bin/redis-server --port 6379 --save "" --appendonly no'

tmux new-session -d -s voice-to-textnote-server \
  -c /Users/ibkim/Project/voice-to-textnote \
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
