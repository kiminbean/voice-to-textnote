# VoiceToTextNote Flutter Client

VoiceToTextNote의 iOS/Android/macOS/Web 클라이언트입니다. 녹음, 서버 기반 STT 파이프라인, 오프라인 STT fallback, 회의록 조회/검색/공유 UI를 제공합니다.

## 현재 구현 상태

### 주요 기능

- 로그인/회원가입: Google/Apple 소셜 로그인 진입점과 게스트 흐름
- 녹음: `record` 기반 녹음, 백그라운드 녹음 서비스, 권한 다이얼로그
- 서버 파이프라인: 업로드 후 STT/Diarization/Minutes/Summary 상태를 SSE 우선, 폴링 fallback으로 추적
- 오프라인 STT: `audio_decoder`로 M4A를 16kHz mono 16-bit WAV로 변환하고 `whisper_ggml_plus`의 `whisper-base` 모델로 기기 내 전사
- 오프라인 청크 처리: 5분 초과 WAV를 30초 PCM 청크로 분할하고 순차 전사 후 텍스트/세그먼트 병합
- 메모리 모니터링: macOS `vm_stat`, Linux `/proc/meminfo`, 기타 플랫폼 RSS 기반 conservative fallback
- 모델 다운로드: CDN fallback URL, `.part` 이어받기, SHA-256 검증, 저장공간 2배+64MB buffer 검사
- 회의록 UI: 결과 보기, 오디오 플레이어, 화자 세그먼트, 검색, 템플릿, 팀 공유, 내보내기
- 알림/딥링크: Firebase Messaging 토큰 처리, 완료 알림, meeting deep link 소비

### 남은 제약

- 네이티브 MethodChannel STT 플러그인은 deprecated skeleton 상태이며, 실제 전사는 `whisper_ggml_plus` 경로가 담당합니다.
- `progressStream`은 현재 `WhisperSttServiceImpl`에서 빈 스트림입니다. 오프라인 진행률은 `OfflineSttService.transcribeWithProgress()`의 청크 단위 진행률로 노출됩니다.
- iOS/Android 저장공간과 가용 메모리는 플랫폼 전용 API가 아니라 Dart fallback을 사용합니다. 실제 OS API 연동은 후속 하드닝 대상입니다.
- `ModelDownloadDialog`에는 아직 샘플 URL/경로/체크섬이 남아 있어 실제 릴리스 전 모델 메타데이터 주입이 필요합니다.
- `lib/dataconnect_generated/`는 Firebase Data Connect generated code를 포함하지만 현재 `firebase_data_connect` 의존성이 없어 전체 `dart analyze lib test`를 실패시킵니다.

## 디렉토리 구조

```text
lib/
├── config/                 # 앱/Firebase 설정
├── models/                 # API 및 UI 모델
├── providers/              # Riverpod 상태 관리
├── router/                 # GoRouter 라우팅
├── screens/                # 주요 화면
├── services/               # API, STT, 녹음, 다운로드, 알림 서비스
└── widgets/                # 재사용 UI 컴포넌트

test/
├── config/
├── models/
├── providers/
├── screens/
├── services/
└── widgets/
```

## 오프라인 STT 흐름

1. `AudioPreprocessor.convertToWav()`가 입력 오디오를 16kHz mono 16-bit WAV로 변환합니다.
2. `OfflineSttService.transcribeWithProgress()`가 WAV 길이를 추정합니다.
3. 5분 이하는 단일 전사, 5분 초과는 30초 PCM 청크로 분할합니다.
4. 각 청크 처리 전에 `MemoryChecker.hasSufficientMemory()`로 메모리 여유를 확인합니다.
5. `WhisperSttServiceImpl`이 필요 시 `whisper-base` 모델을 다운로드하고 전사합니다.
6. 청크 결과는 텍스트 join과 타임스탬프 offset 적용으로 병합되며 임시 청크 파일은 즉시 삭제됩니다.

## 모델 다운로드 흐름

- 기본 CDN: `https://cdn.voice-to-textnote.com/models`
- 명시 URL이 HTTPS가 아니거나 비어 있으면 `/<modelId>.bin` CDN URL로 fallback합니다.
- 다운로드는 `<savePath>.part`에 저장한 뒤 완료 시 원본 경로로 rename합니다.
- 기존 `.part` 파일이 있으면 `Range` 헤더로 이어받기를 시도합니다.
- `downloadAndVerify()`는 선택적으로 `requiredBytes` 기준 저장공간을 먼저 확인하고, 완료 후 SHA-256 체크섬을 검증합니다.

## 개발 명령

```bash
cd client
flutter pub get
flutter run -d chrome
```

변경 파일 단위 분석 예시:

```bash
dart analyze \
  lib/services/memory_checker.dart \
  lib/services/offline_stt_service.dart \
  lib/services/model_download_service.dart \
  lib/providers/model_download_provider.dart \
  test/services/model_download_service_test.dart \
  test/providers/model_download_provider_test.dart
```

`analysis_options.yaml`은 generated/build 산출물(`lib/dataconnect_generated/**`, `build/**`)을 analyzer scope에서 제외합니다. 전체 `flutter analyze lib test`는 현재 generated 의존성 오류 없이 실행되지만, 기존 lint debt가 남아 있어 0-issue 상태는 아닙니다.

## 테스트

```bash
cd client
flutter test
```

현재 테스트 파일은 55개입니다. 이 환경에서는 Flutter SDK cache 쓰기 권한 또는 네트워크 제한으로 `flutter test`/`dart test`가 실패할 수 있습니다.

## 릴리스 전 체크

- 실제 CDN 모델 URL과 SHA-256 체크섬을 릴리스 메타데이터로 연결
- `ModelDownloadDialog`의 샘플 URL/경로/체크섬 제거
- iOS/Android/macOS 실제 디스크/메모리 API 연동
- `whisper_ggml_plus` 모델 다운로드 UX와 오프라인 가용 상태를 실제 기기에서 검증
- `firebase_data_connect` 의존성 또는 generated code 포함 정책 정리
