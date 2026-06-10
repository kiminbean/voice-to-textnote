---
id: SPEC-MOBILE-002
version: "1.0.0"
status: draft
created: "2026-06-10"
updated: "2026-06-10"
author: kisoo
priority: medium
---

# SPEC-MOBILE-002: 구현 계획

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-10 | 초안 작성 | kisoo |

---

## 1. 기술 스택 (Technology Stack)

### 코어 기술

| 기술 | 버전 | 용도 | 선택 이유 |
|------|------|------|----------|
| whisper.cpp | latest (C++ core) | 온디바이스 STT 추론 | 크로스 플랫폼 C++ 코어, iOS/Android/macOS 네이티브 바인딩 가능, 실시간 처리 가능 |
| Flutter Platform Channels | MethodChannel | Dart ↔ 네이티브 통신 | Flutter 공식 메커니즘, 기존 프로젝트와 일관성 |
| Riverpod | 2.6+ | 상태 관리 | 기존 ConnectivityService, PipelineProvider 패턴과 일관성 |
| connectivity_plus | 6.0+ | 네트워크 상태 감지 | 기존 ConnectivityService 재사용 |
| path_provider | 2.1+ | 모델 파일 저장 | Flutter 공식 로컬 저장소 접근 |
| crypto | 3.0+ | SHA-256 체크섬 | 모델 파일 무결성 검증 |
| sqflite | 2.3+ | 로컬 태스크 큐 | 오프라인 결과 보관, 재처리 대상 추적 |

### 플랫폼별 엔진

| 플랫폼 | 엔진 | 가속 | 모델 포맷 |
|--------|------|------|----------|
| iOS | whisper.cpp + Core ML | Neural Engine (ANE) | Core ML (.mlmodelc) |
| macOS | mlx-whisper | MPS (Metal Performance Shaders) | MLX 포맷 (기존 백엔드와 동일) |
| Android | whisper.cpp + TFLite | ARM NEON + NNAPI | TFLite 양자화 (.tflite) |

### 모델 정보

| 항목 | 내용 |
|------|------|
| 모델명 | whisper-base |
| 크기 | ~150MB |
| 한국어 정확도 | ~85% (whisper-large-v3 대비) |
| 처리 속도 | iPhone 15 Pro: ~3x 실시간, Pixel 8: ~2x 실시간 |
| 다운로드 소스 | 프로젝트 CDN 또는 GitHub Releases |

---

## 2. 작업 분해 (Task Decomposition)

### Phase 1: 기반 인프라 (Foundation) — Priority High

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T1-01 | Flutter Platform Channel 인터페이스 정의 | `platform_stt_service.dart` | 없음 |
| T1-02 | 모델 다운로드 서비스 구현 | `model_download_service.dart` | 없음 |
| T1-03 | 모델 버전 관리 및 체크섬 검증 로직 | `model_download_service.dart` (확장) | T1-02 |
| T1-04 | 오디오 전처리 서비스 (M4A → 16kHz WAV) | `audio_preprocessor.dart` | 없음 |
| T1-05 | 로컬 SQLite 태스크 큐 스키마 설계 | `lib/models/offline_task.dart` | 없음 |
| T1-06 | ModelDownloadProvider (Riverpod) 구현 | `model_download_provider.dart` | T1-02 |

### Phase 2: iOS 네이티브 통합 — Priority High

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T2-01 | whisper.cpp iOS 빌드 설정 (Xcode) | `ios/Podfile` 수정, 빌드 스크립트 | T1-01 |
| T2-02 | Core ML 모델 변환 (whisper-base → .mlmodelc) | 변환 스크립트, 모델 번들 | T2-01 |
| T2-03 | WhisperSttPlugin.swift 구현 | `ios/Classes/WhisperSttPlugin.swift` | T2-02 |
| T2-04 | iOS 오디오 전처리 (AVAudioEngine) | Swift 오디오 변환 모듈 | T2-03 |
| T2-05 | iOS 통합 테스트 | 테스트 파일 | T2-04 |

### Phase 3: Android 네이티브 통합 — Priority High

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T3-01 | whisper.cpp Android NDK 빌드 설정 | `android/app/CMakeLists.txt` | T1-01 |
| T3-02 | TFLite 모델 변환 (whisper-base → .tflite) | 변환 스크립트, 모델 파일 | T3-01 |
| T3-03 | WhisperSttPlugin.kt 구현 | `android/.../WhisperSttPlugin.kt` | T3-02 |
| T3-04 | Android 오디오 전처리 (MediaCodec) | Kotlin 오디오 변환 모듈 | T3-03 |
| T3-05 | Android 통합 테스트 | 테스트 파일 | T3-04 |

### Phase 4: macOS 네이티브 통합 — Priority Medium

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T4-01 | mlx-whisper Flutter Plugin 바인딩 | `macos/Classes/MlxWhisperPlugin.swift` | T1-01 |
| T4-02 | macOS 오디오 전처리 (Core Audio) | Swift 오디오 모듈 | T4-01 |
| T4-03 | macOS 통합 테스트 | 테스트 파일 | T4-02 |

### Phase 5: 하이브리드 파이프라인 통합 — Priority High

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T5-01 | HybridPipelineService 구현 (온/오프라인 분기) | `hybrid_pipeline_service.dart` | Phase 2-4 완료 |
| T5-02 | PipelineProvider 수정 (하이브리드 통합) | `pipeline_provider.dart` 수정 | T5-01 |
| T5-03 | OfflineSttProvider 구현 (상태 관리) | `offline_stt_provider.dart` | T5-01 |
| T5-04 | 네트워크 복구 시 자동 재처리 로직 | `hybrid_pipeline_service.dart` 확장 | T5-01 |
| T5-05 | 오프라인/개선됨 결과 배지 UI | `offline_result_badge.dart`, `improved_result_badge.dart` | T5-03 |

### Phase 6: 모델 다운로드 UX — Priority Medium

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T6-01 | 모델 다운로드 다이얼로그 UI | `model_download_dialog.dart` | T1-06 |
| T6-02 | Wi-Fi 감지 및 셀룰러 확인 로직 | `model_download_service.dart` 확장 | T6-01 |
| T6-03 | 다운로드 진행률 표시 (퍼센트 + 예상 시간) | UI 위젯 확장 | T6-01 |
| T6-04 | 다운로드 재개/재시도 에러 핸들링 | 서비스 확장 | T6-01 |

### Phase 7: 통합 테스트 및 검증 — Priority High

| Task ID | 작업 | 산출물 | 선행 조건 |
|---------|------|--------|----------|
| T7-01 | 전체 파이프라인 E2E 테스트 (오프라인 시나리오) | 테스트 파일 | Phase 5 완료 |
| T7-02 | 네트워크 전환 시나리오 테스트 | 테스트 파일 | T7-01 |
| T7-03 | 성능 벤치마크 (처리 시간, 메모리, 배터리) | 벤치마크 리포트 | T7-01 |
| T7-04 | 에지 케이스 테스트 (저용량, 긴 오디오, 중단) | 테스트 파일 | T7-01 |

---

## 3. 위험 분석 (Risk Analysis)

### 높은 위험 (High Risk)

| 위험 | 영향 | 완화 전략 |
|------|------|----------|
| whisper.cpp 모바일 성능 불충분 | 사용자 경험 저하 (STT 처리 지연) | whisper-base 모델 사용 (~150MB, 실시간 2-3x). 5분 초과 시 청크 분할. 벤치마크 선행 |
| Core ML/TFLite 모델 변환 실패 | 플랫폼별 지원 불가 | whisper.cpp 공식 변환 스크립트 사용. 범용 C++ fallback 유지 |
| 모델 다운로드 실패 (네트워크 불안정) | 오프라인 STT 사용 불가 | Resumable download 구현. 3회 자동 재시도. 수동 재시도 UI |
| 배터리 소모 과다 | 사용자 불만 | 5분 초과 녹음 시 경고. 백그라운드 처리 제한. 메모리 모니터링 |

### 중간 위험 (Medium Risk)

| 위험 | 영향 | 완화 전략 |
|------|------|----------|
| 앱 크기 증가 (~150MB 모델) | 앱 스토어 다운로드 저하 | 모델은 앱 번들에 포함하지 않고 최초 실행 시 다운로드 |
| Android 백그라운드 처리 제한 | 긴 오디오 처리 중단 | Foreground Service 활용 (기존 RecordingService 패턴) |
| 플랫폼별 오디오 포맷 차이 | 전처리 오류 | 플랫폼별 오디오 테스트 매트릭스 작성 |
| 오프라인↔온라인 전환 시 데이터 유실 | 결과 손실 | SQLite 태스크 큐로 오프라인 결과 영속 보관 |

### 낮은 위험 (Low Risk)

| 위험 | 영향 | 완화 전략 |
|------|------|----------|
| 모델 버전 업데이트 충돌 | 이전 모델 사용 | 버전 체크 + 백그라운드 업데이트 |
| 다양한 Android 기기 파편화 | 일부 기기 미지원 | TFLite NNAPI fallback. 최소 API 29 제한 |
| macOS mlx-whisper 의존성 충돌 | macOS 클라이언트 빌드 실패 | 기존 백엔드 mlx-whisper와 동일 버전 핀 |

---

## 4. 참조 구현 (Reference Implementations)

### 기존 코드베이스 참조

| 참조 | 파일 | 활용 방법 |
|------|------|----------|
| 플랫폼 적응형 STT | `backend/ml/stt_engine.py` (L19-21) | `_try_load_mlx()`, `_try_load_faster_whisper()` 패턴을 Flutter Platform Channel 분기 로직에 적용 |
| SSE + 폴링 폴백 | `client/lib/providers/pipeline_provider.dart` (L89-99) | `_waitForCompletion()` + Progress Interpolation 패턴을 오프라인 STT 진행률에 재사용 |
| 네트워크 감지 | ConnectivityService + OfflineBanner | `connectivity_plus` 기반 상태 모니터링을 하이브리드 파이프라인 분기에 활용 |
| 백그라운드 녹음 | BackgroundRecordingService + RecordingProvider | 백그라운드 처리 패턴을 긴 오디오 STT 처리에 적용 |
| Celery 훅 | `backend/workers/tasks/transcription_task.py` | 청크 분할 로직 (L50-51, 30분 초과 시)을 클라이언트 측 5분 분할에 참조 |
| 오디오 전처리 | `backend/ml/stt_engine.py` transcribe() | 16kHz mono WAV 변환 로직을 Flutter 클라이언트 측에 동일 적용 |

### 외부 참조

| 참조 | URL | 활용 방법 |
|------|-----|----------|
| whisper.cpp | github.com/ggerganov/whisper.cpp | C++ 코어 빌드, iOS/Android 플랫폼 예제 |
| Core ML Whisper | github.com/ggerganov/whisper.cpp/tree/master/coreml | iOS Core ML 모델 변환 가이드 |
| TFLite Whisper | github.com/usefulsensors/openai-whisper | Android TFLite 모델 변환 가이드 |
| mlx-whisper | github.com/ml-explore/mlx-examples | macOS mlx-whisper Dart 바인딩 참조 |

---

## 5. 델타 마커 (Delta Markers)

본 SPEC은 기존 코드베이스에 대한 변경을 최소화하는 브라운필드 접근 방식을 따른다.

### 신규 파일 (Greenfield)

- `client/lib/services/offline_stt_service.dart`
- `client/lib/services/model_download_service.dart`
- `client/lib/services/audio_preprocessor.dart`
- `client/lib/services/hybrid_pipeline_service.dart`
- `client/lib/services/platform_stt_service.dart`
- `client/lib/providers/offline_stt_provider.dart`
- `client/lib/providers/model_download_provider.dart`
- `client/lib/models/model_info.dart`
- `client/lib/widgets/model_download_dialog.dart`
- `client/lib/widgets/offline_result_badge.dart`
- `client/lib/widgets/improved_result_badge.dart`
- `client/ios/Classes/WhisperSttPlugin.swift`
- `client/macos/Classes/MlxWhisperPlugin.swift`
- `client/android/app/src/main/kotlin/com/voicetextnote/app/WhisperSttPlugin.kt`

### 수정 파일 (Brownfield Delta)

| 파일 | 변경 범위 | 변경 내용 |
|------|----------|----------|
| `client/lib/providers/pipeline_provider.dart` | MODERATE | 하이브리드 파이프라인 분기 로직 추가 (오프라인 감지 시 로컬 STT 경로) |
| `client/lib/models/stt_result.dart` | MINOR | `offline: bool` 필드 추가 |
| `client/lib/screens/recording_screen.dart` | MINOR | 오프라인 STT 트리거 로직 추가 |
| `client/pubspec.yaml` | MINOR | 의존성 4개 추가 (path_provider, crypto, sqflite, 추가) |
| `client/lib/services/connectivity_service.dart` | MINOR | 하이브리드 파이프라인을 위한 상태 이벤트 확장 |

---

## 6. 마일스톤 (Milestones)

### Primary Goal: 오프라인 STT 최소 기능

- Phase 1 (기반 인프라) 완료
- Phase 2 (iOS) 또는 Phase 3 (Android) 중 1개 플랫폼 완료
- Phase 5 (하이브리드 파이프라인) 핵심 로직 완료
- 오프라인 상태에서 녹음 후 로컬 STT 처리 → 결과 표시 가능

### Secondary Goal: 전 플랫폼 지원

- Phase 2 (iOS) + Phase 3 (Android) + Phase 4 (macOS) 모두 완료
- Phase 6 (모델 다운로드 UX) 완료
- 네트워크 복구 시 자동 재처리 동작

### Final Goal: 품질 검증 완료

- Phase 7 (통합 테스트) 완료
- 성능 벤치마크 기준 충족
- 에지 케이스 테스트 통과

---

*SPEC ID: SPEC-MOBILE-002*
*문서: plan.md*
