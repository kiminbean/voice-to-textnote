# STT / Diarization Processing Runbook

작성일: 2026-06-27

이 문서는 iPhone 앱에서 녹음 완료 후 `STT 처리중 20%`에 머무르는 문제를 재발하지 않도록 원인, 확인 순서, 수정 이력, 빌드 방법을 정리한 운영 메모다.

## 현재 기준값

- iPhone device ID: `00008150-000239020C08401C`
- Backend base URL: `http://100.69.69.119:8000/api/v1`
- Local project path: `/Users/ibkim/Projects/voice-to-textnote`
- Server project path: `/Users/ibkim/Projects/voice-to-textnote`
- Latest confirmed fix commit: `537a0ac Keep STT progress from stalling on SSE gaps`
- Mac mini backend API supervisor: LaunchAgent `com.voicetextnote.backend-api`

## 20%의 의미

앱에서 20%는 업로드 실패 지점이 아니다.

`client/lib/providers/pipeline_provider.dart`는 업로드 성공 후 서버가 `task_id`를 반환하면 다음 상태를 만든다.

```text
currentStep: PipelineStep.transcribing
progress: 0.2
currentTaskId: sttTaskId
```

따라서 20%에서 멈춘 것처럼 보이면 실제 의미는 다음 중 하나다.

- STT/DIA 태스크가 서버에서 아직 처리 중이다.
- 서버 작업은 끝났지만 앱이 SSE 완료 이벤트를 받지 못했다.
- SSE가 인증 실패로 닫히고 polling fallback도 제대로 작동하지 못했다.
- 앱이 서버 재시작 전에 생성된 오래된 task를 기다리고 있다.

## 먼저 확인할 것

서버 자체가 처리 가능한지 먼저 확인한다.

```bash
launchctl print gui/$(id -u)/com.voicetextnote.backend-api | rg 'state =|pid =|properties ='

curl -sS -o /tmp/vtt_health.out -w 'health:%{http_code}\n' \
  http://100.69.69.119:8000/api/v1/health

curl -sS -o /tmp/vtt_openapi.out -w 'openapi:%{http_code}\n' \
  http://100.69.69.119:8000/openapi.json

curl -sS -o /tmp/vtt_guest.out -w 'guest:%{http_code}\n' \
  -X POST http://100.69.69.119:8000/api/v1/auth/guest
```

기대값:

```text
state = running
health:200
openapi:200
guest:200
```

API 프로세스가 꺼져 있거나 재부팅 후 올라오지 않았다면 수동 `tmux` 세션을 만들지 말고
아래 명령으로 LaunchAgent를 설치/재시작한다.

```bash
cd /Users/ibkim/Projects/voice-to-textnote
./scripts/install_backend_api_launch_agent.sh
```

## 실제 원인과 수정

이번 문제의 핵심 원인은 앱의 SSE 경로가 일반 API 경로와 인증 방식이 달랐다는 점이다.

일반 API는 `client/lib/services/api_client.dart`의 인터셉터가 아래 헤더를 넣는다.

- `X-API-Key`, 또는
- `Authorization: Bearer <access-token>`, 또는
- `Authorization: Bearer guest:<guest-token>`

하지만 기존 `SseService`는 API key만 보냈고, guest/user bearer token은 보내지 않았다. 서버가 task stream을 보호하면 SSE가 인증 실패할 수 있다.

추가로 STT와 DIA는 병렬 대기한다. 기존 `SseService`가 내부 HTTP client를 하나만 들고 있으면 두 스트림이 서로 간섭할 수 있었다.

`537a0ac`에서 적용한 수정:

- `SseService`에 async `headersProvider` 추가
- `sseServiceProvider`에서 일반 API와 동일한 인증 헤더 주입
- SSE HTTP 응답이 2xx가 아니면 예외를 던져 polling fallback으로 전환
- `connect()`마다 독립 `http.Client` 생성
- `disconnect()`는 열린 모든 SSE client를 닫음
- 10초 idle timeout 후 polling fallback
- `ProcessingScreen`이 직접 `SseService`를 만들지 않고 `sseServiceProvider`를 사용

## 서버 검증 증거

2026-06-27에 로컬에서 작은 WAV 파일로 실제 서버 처리 검증을 수행했다.

확인된 내용:

- guest token 발급 성공
- `POST /api/v1/transcriptions` 성공
- STT task 생성
- DIA task 생성
- STT status가 `completed`
- DIA status가 `completed`
- guest bearer token으로 `/api/v1/tasks/{task_id}/stream` 요청 시 `HTTP 200`
- SSE body에서 `event: status_update` 수신

이 증거가 있으면 서버 STT/DIA 전체 파이프라인은 동작 중이며, 앱 표시 문제는 클라이언트 진행 수신 경로를 우선 의심한다.

## iPhone 릴리스 빌드

사용자가 홈 화면에서 직접 실행해 확인할 때는 release 또는 profile 빌드를 설치한다. debug 앱은 Flutter tooling 없이 실행하면 종료될 수 있다.

최종 성공한 릴리스 설치 명령:

```bash
cd /Users/ibkim/Projects/voice-to-textnote/client
flutter run --release --no-pub --no-resident \
  -d 00008150-000239020C08401C \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

2026-06-27 결과:

```text
Xcode build done
Installing and launching
사용자 확인: 잘됩니다.
```

## 재발 방지 체크리스트

STT가 20%에서 멈추면 순서대로 확인한다.

1. 현재 앱 빌드가 `API_BASE_URL=http://100.69.69.119:8000/api/v1`로 설치됐는지 확인한다.
2. `com.voicetextnote.backend-api` LaunchAgent가 `running`인지 확인한다.
3. 서버 `/api/v1/health`, `/openapi.json`, `/auth/guest`가 200인지 확인한다.
4. 실제 WAV probe로 STT/DIA task가 completed 되는지 확인한다.
5. task stream이 guest/user bearer auth로 `200`을 반환하는지 확인한다.
6. 클라이언트 `SseService`가 인증 헤더를 넣는지 확인한다.
7. STT/DIA 병렬 대기 중 SSE client가 서로 닫히지 않는지 확인한다.
8. 서버 재시작 직전 생성된 오래된 task를 앱이 기다리는 상황이면 앱을 완전히 종료하고 새 녹음을 시작한다.

## Android staging release 재설치 기준

Android 실기기에서 새 기능 메뉴가 보이지 않으면 먼저 오래된 APK 설치 여부를 확인한다.
2026-07-01 `Redmi Note 9 Pro`에서는 결과 화면 탭이 11개로 표시되며 `약속 레이더`가
빠진 원인이 stale release APK였다. 최신 staging release 재설치 후 탭이 12개로 바뀌고
`약속 레이더`가 4번째 탭으로 표시됐다.

```bash
cd /Users/ibkim/Projects/voice-to-textnote/client
flutter run --release --no-pub --no-resident \
  -d 76aadc20 \
  --dart-define=ENV=staging \
  --dart-define=API_BASE_URL=http://100.69.69.119:8000/api/v1
```

검증:

```bash
adb shell dumpsys package com.voicetextnote.app | rg 'lastUpdateTime|versionName|versionCode'
adb shell uiautomator dump /sdcard/window.xml >/dev/null
adb shell cat /sdcard/window.xml | tr '<' '\n' | rg '약속 레이더|탭 12개'
unzip -p build/app/outputs/flutter-apk/app-release.apk lib/arm64-v8a/libapp.so \
  | strings | rg '100\.69\.69\.119|api\.voicetextnote\.com'
```

자동 gate:

```bash
cd /Users/ibkim/Projects/voice-to-textnote
python3 client/scripts/verify_promise_radar_device_gate.py --serial 76aadc20
```

이 스크립트는 `dumpsys package` 설치 metadata, UIAutomator의 `약속 레이더`/`탭 12개`,
APK 내부 staging API URL과 production host 미사용을 함께 검증한다.

## 검증 명령

클라이언트 수정 후 최소 검증:

```bash
cd client
flutter test --no-pub test/services/sse_service_test.dart test/providers/pipeline_provider_test.dart
flutter analyze --no-pub
```

빌드나 테스트 중 아래 파일들이 자동으로 흔들릴 수 있다.

```text
client/pubspec.lock
client/ios/Podfile.lock
client/ios/Runner.xcodeproj/project.pbxproj
client/*/GeneratedPluginRegistrant.*
client/**/Package.resolved
```

이 파일들이 실제 의존성 변경이 아니라 `flutter clean`, `flutter pub get`, `flutter run`의 부산물이면 커밋 전에 되돌린다.
