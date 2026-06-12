---
id: SPEC-MOBILE-003
version: "1.0.0"
status: partial
created: "2026-06-11"
updated: "2026-06-12"
author: sisyphus
priority: high
depends_on: SPEC-MOBILE-002
---

# SPEC-MOBILE-003: 오프라인 STT 프로덕션 하드닝

## 1. 개요

SPEC-MOBILE-002에서 구현된 오프라인 STT 하이브리드 파이프라인의 **스켈레톤 코드를 프로덕션 수준으로 교체**합니다.

2026-06-12 현재 코드 기준으로 P0 일부와 P1/P2 일부가 구현되었습니다. `AudioPreprocessor`는 `audio_decoder` 기반 실제 WAV 변환을 호출하고, `PlatformSttService`의 주 경로는 `whisper_ggml_plus`입니다. 긴 WAV는 `OfflineSttService`에서 30초 PCM 청크로 실제 분할됩니다. 다만 iOS/Android 네이티브 메모리/저장공간 Platform Channel, 네이티브 진행률 EventChannel, 실제 릴리스 모델 manifest 연결은 아직 남아 있습니다.

## 2. 범위

### In Scope
- **P0 완료/부분**: 오디오 전처리 실제 변환 (M4A → 16kHz mono WAV) via `audio_decoder`
- **P0 부분**: `whisper_ggml_plus` 기반 실제 추론 경로. 기존 MethodChannel 플러그인은 deprecated skeleton.
- **P1 부분**: 메모리 모니터링 Dart fallback 구현 (`vm_stat`, `/proc/meminfo`, RSS fallback)
- **P1 미완료**: 진행률 EventChannel 네이티브 구현
- **P1 완료**: 실제 오디오 청크 분할 로직
- **P2 부분**: 모델 다운로드 CDN fallback + 체크섬 검증 흐름
- **P2 부분**: macOS/Linux 디스크 저장공간 확인. iOS/Android native storage API는 미완료.

### Out of Scope
- 화자 분리(Diarization) 오프라인 처리 (별도 SPEC)
- 실제 디바이스 성능 벤치마크 (QA 단계에서 수행)
- UI/UX 변경 (기존 위젯 유지)

## 3. 기술 결정

### 3.1 오디오 변환: `audio_decoder` 패키지 채택

**결정**: `ffmpeg-kit` 대신 `audio_decoder` (^0.8.1) 사용

**근거**:
- 앱 사이즈 증가 ~500KB vs FFmpeg 15-30MB
- Native Platform API 사용 (iOS: AVFoundation, Android: MediaCodec, macOS: AVFoundation)
- sampleRate/channels/bitDepth 파라미터 직접 제어
- FFmpeg 의존성 없음 → 빌드 복잡도 감소
- 2026-06 활성 유지보수, 크리티컬 버그 없음

### 3.2 Whisper 엔진: `whisper_ggml_plus` 패키지 검증 후 채택/폴백

**Primary**: `whisper_ggml_plus` + `whisper_ggml_plus_ffmpeg` 통합 패키지
**Fallback**: 기존 MethodChannel 유지 + whisper.cpp 수동 빌드

**검증 기준**:
- pub.dev 점수 80+ 및 활성 유지보수
- iOS/Android/macOS 3플랫폼 지원
- GGML 모델 포맷 지원
- 메모리 사용량 합리적 (whisper-base ~150MB)

### 3.3 청크 분할: PCM 바이트 직접 분할

WAV 변환 후 16kHz mono 16-bit PCM이므로:
- 1초당 32,000 bytes (16000 samples × 2 bytes)
- 30초 청크 = 960,000 bytes
- WAV 헤더(44 bytes) 제외 후 PCM 데이터를 바이트 오프셋으로 분할

**구현 상태**: `client/lib/services/offline_stt_service.dart`가 WAV 전체를 매번 읽지 않고 `RandomAccessFile`로 대상 PCM byte range만 읽어 청크 WAV를 생성합니다. 각 청크 처리 후 임시 파일과 부모 임시 디렉터리를 삭제합니다.

## 4. 요구사항 (EARS Format)

### REQ-MOBILE-012: 프로덕션 오디오 전처리

> The system **shall** convert M4A audio files to 16kHz mono 16-bit PCM WAV format using native platform audio APIs, when the user initiates offline STT processing.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-012-01 | `audio_decoder` 패키지 통합으로 M4A→WAV 실제 변환 | P0 |
| REQ-MOBILE-012-02 | 변환 실패 시 명확한 에러 메시지 + 원본 파일 보존 | P0 |
| REQ-MOBILE-012-03 | 변환 후 WAV 헤더 검증 (RIFF, 16kHz, mono, 16-bit) | P0 |
| REQ-MOBILE-012-04 | 빈 파일/손상 파일 입력 시 ArgumentError/FileSystemException | P0 |

### REQ-MOBILE-013: 네이티브 Whisper 추론 연동

> The system **shall** perform on-device Whisper inference using a Flutter whisper package, when a valid WAV file is provided through the offline STT pipeline.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-013-01 | iOS whisper.cpp 또는 통합 패키지로 실제 추론 | P0 |
| REQ-MOBILE-013-02 | macOS mlx-whisper 또는 통합 패키지로 실제 추론 | P0 |
| REQ-MOBILE-013-03 | Android whisper.cpp/TFLite 또는 통합 패키지로 실제 추론 | P0 |
| REQ-MOBILE-013-04 | 추론 결과에 타임스탬프 세그먼트 포함 | P0 |
| REQ-MOBILE-013-05 | 모델 미로드 시 isAvailable=false + 명확한 에러 | P0 |
| REQ-MOBILE-013-06 | 추론 진행률 0.0~1.0 EventChannel 스트리밍 | P1 |

### REQ-MOBILE-014: 실제 메모리/저장공간 모니터링

> The system **shall** query actual device memory availability before starting offline STT processing, and **shall not** proceed if available memory is insufficient.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-014-01 | iOS: os_proc_available_memory() / NSProcessInfo | P1 |
| REQ-MOBILE-014-02 | Android: ActivityManager.MemoryInfo | P1 |
| REQ-MOBILE-014-03 | macOS: mach_task_info / vm_statistics | P1 |
| REQ-MOBILE-014-04 | 최소 512MB 가용 메모리 미충족 시 안전 중단 | P1 |
| REQ-MOBILE-014-05 | 디스크 여유공간 실제 조회 (300MB 기준) | P2 |

**구현 상태**: `MemoryChecker`가 macOS `vm_stat`, Linux `/proc/meminfo`, 기타 플랫폼 RSS fallback을 제공합니다. iOS/Android 전용 native API와 macOS `mach_task_info` 직접 호출은 미구현입니다. 디스크 저장공간은 `ModelDownloadService`가 macOS/Linux에서 `df -Pk`를 사용하고 기타 플랫폼은 안전 fallback을 사용합니다.

### REQ-MOBILE-015: 실제 오디오 청크 분할

> The system **shall** split audio files exceeding 5 minutes into 30-second PCM chunks for sequential processing, when the estimated duration exceeds the chunk threshold.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-015-01 | WAV PCM 데이터 바이트 오프셋 기반 30초 분할 | P1 |
| REQ-MOBILE-015-02 | 각 청크에 올바른 WAV 헤더 prepend | P1 |
| REQ-MOBILE-015-03 | 분할된 청크 순차 처리 후 결과 텍스트 병합 | P1 |
| REQ-MOBILE-015-04 | 청크 임시 파일 처리 완료 후 즉시 삭제 | P1 |

**구현 상태**: 구현 완료. 진행률은 청크 단위로 0~100%를 emit합니다.

### REQ-MOBILE-016: 모델 다운로드 프로덕션 구성

> The system **shall** download Whisper model files from a configured CDN endpoint, when the model is not available locally.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-016-01 | 실제 HuggingFace/GitHub Releases CDN URL 구성 | P2 |
| REQ-MOBILE-016-02 | SHA-256 체크섬 실제 검증 로직 연동 | P2 |
| REQ-MOBILE-016-03 | ModelDownloadDialog 하드코딩 URL 제거 | P2 |
| REQ-MOBILE-016-04 | 저장공간 확인 시 실제 디스크 여유공간 사용 | P2 |

**구현 상태**: `ModelDownloadService.resolveDownloadUrl()`은 HTTPS URL을 그대로 쓰고, 없거나 안전하지 않으면 `https://cdn.voice-to-textnote.com/models/<modelId>.bin`으로 fallback합니다. `.part` 이어받기, SHA-256 검증, 저장공간 2배+64MB buffer 검사는 구현됐습니다. 실제 HuggingFace/GitHub Releases URL 및 체크섬 manifest와 `ModelDownloadDialog` 연동은 미완료입니다.

## 5. 제약 조건

- Flutter SDK >= 3.4.4, Dart >= 3.4.4
- Android minSdkVersion 29, targetSdkVersion 34
- iOS deployment target: 프로젝트 기본값
- macOS deployment target: 10.15
- 기존 MethodChannel 인터페이스(`com.voicetextnote/whisper_stt`) 유지 또는 패키지 내부 추상화로 교체
- 기존 테스트 374개 회귀 없이 통과 필요

## 6. 위험 및 완화

| 위험 | 확률 | 영향 | 완화 |
|------|------|------|------|
| `whisper_ggml_plus` 미성숙 | 중 | 높음 | 폴백: 기존 MethodChannel + 수동 whisper.cpp 빌드 |
| `audio_decoder` 특정 기기 변환 실패 | 낮 | 중 | 변환 후 WAV 헤더 검증 + 에러 핸들링 |
| 앱 사이즈 증가 (모델 포함 시) | 높음 | 중 | 모델 다운로드 on-demand (앱 번들 미포함) |
| Apple App Store 심사 (네이티브 코드) | 중 | 높음 | whisper.cpp 오픈소스 라이선스 명시 |
