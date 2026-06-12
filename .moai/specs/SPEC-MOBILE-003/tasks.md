---
id: SPEC-MOBILE-003
version: "1.0.0"
status: partial
updated: "2026-06-12"
---

# SPEC-MOBILE-003 Tasks

## Batch 1: P0 — 오디오 전처리 + Whisper 엔진 조사 (T-001~T-004)

### T-001: `audio_decoder` 패키지 통합 및 AudioPreprocessor 교체
- **Status**: ✅ Done
- **Target**: `client/lib/services/audio_preprocessor.dart`, `client/pubspec.yaml`
- **Description**: 시뮬레이션 WAV 헤더 생성을 `audio_decoder` 패키지를 사용한 실제 M4A→WAV 변환으로 교체
- **Acceptance**:
  - `convertToWav()`가 실제로 M4A를 16kHz mono 16-bit PCM WAV로 변환
  - 변환 후 WAV 파일의 RIFF 헤더, sample_rate=16000, channels=1 검증
  - 빈 파일/손상 파일 입력 시 적절한 예외 발생
  - 기존 테스트(9개) 모두 통과 (mock 기반)
- **Dependencies**: None

### T-002: `audio_decoder` 변환 통합 테스트 작성
- **Status**: ✅ Done
- **Target**: `client/test/services/audio_preprocessor_test.dart`
- **Description**: audio_decoder 통합 후 회귀 테스트 + 실제 변환 검증 테스트
- **Acceptance**:
  - 기존 9개 단위 테스트 유지
  - 변환 실패 케이스 에러 핸들링 테스트 추가
  - dart analyze 0 errors
- **Dependencies**: T-001

### T-003: Whisper Flutter 패키지 프로덕션 적합성 검증
- **Status**: ✅ Done
- **Target**: 조사 결과 문서화
- **Description**: `whisper_ggml_plus` 패키지의 프로덕션 적합성 검증 (pub.dev 점수, GitHub 활성도, iOS/Android/macOS 지원, 메모리 프로파일)
- **Acceptance**:
  - 패키지 선택 근거 문서화 (pub.dev 점수, GitHub stars, 최근 커밋)
  - 3플랫폼 빌드 가능성 확인
  - 메모리 사용량 추정치 확보
  - 선택/폴백 전략 확정
- **Dependencies**: None

### T-004: 선택된 Whisper 패키지 pubspec.yaml 추가
- **Status**: ✅ Done
- **Target**: `client/pubspec.yaml`
- **Description**: 검증된 whisper 패키지를 pubspec.yaml에 추가하고 flutter pub get 실행
- **Acceptance**:
  - pubspec.yaml에 패키지 추가
  - `flutter pub get` 성공
  - `dart analyze` 0 errors
- **Dependencies**: T-003

## Batch 2: P0 — 네이티브 STT 엔진 실제 연동 (T-005~T-010)

### T-005: PlatformSttService 추상화 리팩토링
- **Status**: ✅ Done
- **Target**: `client/lib/services/platform_stt_service.dart`
- **Description**: whisper 패키지 선택에 따라 PlatformSttService 인터페이스를 패키지 네이티브 API에 맞게 조정 (MethodChannel 직접 사용 vs 패키지 내부 추상화)
- **Acceptance**:
  - 패키지 API와 기존 PlatformSttService 인터페이스 매핑
  - 기존 12개 테스트 유지
  - dart analyze 0 errors
- **Dependencies**: T-004

### T-006: iOS WhisperSttPlugin 실제 추론 구현
- **Status**: ⏳ Deferred
- **Target**: `client/ios/Classes/WhisperSttPlugin.swift`
- **Description**: iOS whisper.cpp 또는 통합 패키지를 사용하여 transcribe 메서드를 실제 구현
- **Acceptance**:
  - `transcribe` 메서드가 실제 오디오 파일을 처리하여 텍스트 반환
  - `isAvailable`이 모델 로드 상태에 따라 동적 반환
  - 에러 발생 시 FlutterError로 명확한 에러 전달
  - 결과에 segments, language, confidence 포함
- **Dependencies**: T-005

### T-007: macOS MlxWhisperPlugin 실제 추론 구현
- **Status**: ⏳ Deferred
- **Target**: `client/macos/Classes/MlxWhisperPlugin.swift`
- **Description**: macOS mlx-whisper 또는 통합 패키지를 사용하여 transcribe 메서드를 실제 구현
- **Acceptance**:
  - `transcribe` 메서드가 실제 오디오 파일을 처리하여 텍스트 반환
  - MPS 가속 사용 가능 시 활용
  - 결과에 segments, language, confidence 포함
- **Dependencies**: T-005

### T-008: Android WhisperSttPlugin 실제 추론 구현
- **Status**: ⏳ Deferred
- **Target**: `client/android/.../WhisperSttPlugin.kt`, `client/android/app/build.gradle`
- **Description**: Android whisper.cpp/TFLite 또는 통합 패키지를 사용하여 transcribe 메서드를 실제 구현
- **Acceptance**:
  - `transcribe` 메서드가 실제 오디오 파일을 처리하여 텍스트 반환
  - ARM NEON 최적화 활용 가능 시 활용
  - 결과에 segments, language, confidence 포함
  - build.gradle에 필요한 네이티브 의존성 추가
- **Dependencies**: T-005

### T-009: OfflineSttService 실제 엔진 통합 테스트
- **Status**: ✅ Partial
- **Target**: `client/test/services/offline_stt_service_test.dart`
- **Description**: 실제 whisper 엔진 연동 후 OfflineSttService 통합 테스트
- **Acceptance**:
  - 기존 테스트 유지
  - 새 통합 테스트 추가 (모델 로드, 추론, 에러 핸들링)
  - dart analyze 0 errors
- **Dependencies**: T-006, T-007, T-008

### T-010: P0 통합 검증 — 전체 오프라인 파이프라인 E2E
- **Status**: ⏳ Pending
- **Target**: 전체 오프라인 파이프라인
- **Description**: AudioPreprocessor → OfflineSttService → HybridPipelineService 전체 흐름 E2E 검증
- **Acceptance**:
  - M4A 파일 → 실제 WAV 변환 → 실제 whisper 추론 → 텍스트 결과
  - 오프라인 결과에 `offline: true` 메타데이터 포함
  - dart analyze 0 errors
  - 기존 374개 테스트 모두 통과
- **Dependencies**: T-002, T-009

## Batch 3: P1 — 메모리 모니터링 + 진행률 + 청크 분할 (T-011~T-016)

### T-011: 메모리 모니터링 Platform Channel 인터페이스 정의
- **Status**: ✅ Partial
- **Target**: `client/lib/services/platform_stt_service.dart` (또는 신규 파일)
- **Description**: 메모리 가용 여부 확인을 위한 Platform Channel 인터페이스 정의
- **Acceptance**:
  - `getAvailableMemory()` 메서드 추가
  - Dart 추상 인터페이스 + MethodChannel 구현
  - 단위 테스트 작성
- **Dependencies**: T-005

### T-012: iOS/macOS 메모리 모니터링 네이티브 구현
- **Status**: ✅ Partial
- **Target**: `client/ios/Classes/WhisperSttPlugin.swift`, `client/macos/Classes/MlxWhisperPlugin.swift`
- **Description**: iOS: os_proc_available_memory(), macOS: vm_statistics64로 실제 가용 메모리 조회
- **Acceptance**:
  - `getAvailableMemory` 메서드가 실제 바이트 수 반환
  - 512MB 미만 시 false 반환
  - 단위 테스트
- **Dependencies**: T-011

### T-013: Android 메모리 모니터링 네이티브 구현
- **Status**: ⏳ Deferred
- **Target**: `client/android/.../WhisperSttPlugin.kt`
- **Description**: ActivityManager.MemoryInfo로 실제 가용 메모리 조회
- **Acceptance**:
  - `getAvailableMemory` 메서드가 실제 바이트 수 반환
  - 512MB 미만 시 false 반환
- **Dependencies**: T-011

### T-014: OfflineSttService 메모리 체크 실제 연동
- **Status**: ✅ Partial
- **Target**: `client/lib/services/offline_stt_service.dart`
- **Description**: `_hasSufficientMemory()` 시뮬레이션을 실제 Platform Channel 호출로 교체
- **Acceptance**:
  - `_hasSufficientMemory()`가 실제 디바이스 메모리 조회
  - 512MB 미만 시 `TranscriptionStatus.failed` + 에러 메시지
  - 기존 테스트 유지
- **Dependencies**: T-012, T-013

### T-015: 진행률 EventChannel 네이티브 구현 (3플랫폼)
- **Status**: ⏳ Deferred
- **Target**: 모든 네이티브 플러그인 파일
- **Description**: `com.voicetextnote/whisper_stt_progress` EventChannel을 3플랫폼에 구현
- **Acceptance**:
  - 추론 중 진행률 0.0~1.0 실시간 스트리밍
  - iOS/Android/macOS 모두 구현
  - 기존 Dart EventChannel 수신 코드와 호환
- **Dependencies**: T-006, T-007, T-008

### T-016: 실제 오디오 청크 분할 구현
- **Status**: ✅ Done
- **Target**: `client/lib/services/offline_stt_service.dart`
- **Description**: PCM 바이트 오프셋 기반 30초 청크 분할 + WAV 헤더 prepend + 순차 처리 + 결과 병합
- **Acceptance**:
  - 5분 초과 오디오를 30초 PCM 청크로 실제 분할
  - 각 청크에 올바른 WAV 헤더 prepend
  - 청크 순차 처리 후 텍스트 병합
  - 청크 임시 파일 처리 후 즉시 삭제
  - 진행률 정확한 퍼센트 업데이트
- **Dependencies**: T-001, T-005

## Batch 4: P2 — 모델 다운로드 프로덕션 구성 (T-017~T-019)

### T-017: 모델 다운로드 CDN URL + 체크섬 실제 구성
- **Status**: ✅ Partial
- **Target**: `client/lib/services/model_download_service.dart`, `client/lib/providers/model_download_provider.dart`
- **Description**: 하드코딩된 URL/체크섬을 실제 HuggingFace/GitHub Releases URL로 교체
- **Acceptance**:
  - whisper-base GGML 모델 다운로드 URL 구성 (HuggingFace 또는 GitHub Releases)
  - SHA-256 체크섬 실제 검증 로직 연동
  - ModelDownloadProvider 시뮬레이션 제거
  - 기존 테스트 유지
- **Dependencies**: T-003

### T-018: ModelDownloadDialog 하드코딩 제거
- **Status**: ⏳ Pending
- **Target**: `client/lib/widgets/model_download_dialog.dart`
- **Description**: 하드코딩된 `https://example.com/model.bin` 등을 실제 URL로 교체
- **Acceptance**:
  - 하드코딩 URL/경로/체크섬 제거
  - ModelDownloadService에서 실제 값 주입
  - 기존 8개 위젯 테스트 유지
- **Dependencies**: T-017

### T-019: 디스크 저장공간 실제 확인
- **Status**: ✅ Partial
- **Target**: `client/lib/services/model_download_service.dart`
- **Description**: `hasSufficientStorage()` 시뮬레이션을 Platform Channel 기반 실제 디스크 여유공간 조회로 교체
- **Acceptance**:
  - 300MB 미만 여유공간 시 다운로드 차단
  - iOS/Android/macOS 모두 실제 조회
  - 기존 테스트 유지
- **Dependencies**: T-011

## Task Summary

| Batch | Tasks | Priority | Dependencies |
|-------|-------|----------|-------------|
| Batch 1 | T-001~T-004 | P0 | None |
| Batch 2 | T-005~T-010 | P0 | Batch 1 |
| Batch 3 | T-011~T-016 | P1 | Batch 2 |
| Batch 4 | T-017~T-019 | P2 | Batch 2 |
| **Total** | **19 tasks** | | |

## 2026-06-12 Implementation Notes

- P0 STT 추론의 실제 경로는 `whisper_ggml_plus`입니다. iOS/macOS/Android MethodChannel 플러그인은 deprecated skeleton으로 남아 있습니다.
- 메모리 모니터링은 Platform Channel이 아니라 `MemoryChecker` Dart fallback입니다.
- 청크 분할은 `OfflineSttService`에서 구현 완료됐습니다.
- 모델 다운로드 provider는 실제 `ModelDownloadService`를 사용하지만, `ModelDownloadDialog`는 아직 샘플 URL/경로/체크섬을 전달합니다.
- 저장공간 확인은 macOS/Linux `df -Pk`와 테스트 주입 seam을 사용합니다. iOS/Android 전용 API는 남아 있습니다.
- 변경 파일 단위 `dart analyze`는 통과했지만 전체 분석/테스트는 기존 generated dependency와 sandbox 제한으로 차단됐습니다.
