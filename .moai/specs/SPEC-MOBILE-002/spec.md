---
id: SPEC-MOBILE-002
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-15"
author: Sisyphus
priority: medium
issue_number: 20
depends_on: SPEC-MOBILE-001
---

# SPEC-MOBILE-002: 오프라인 STT 처리 (On-Device Whisper)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 초기 작성 | Sisyphus |
| 1.0.1 | 2026-06-14 | Flutter 로컬 STT MethodChannel 계약, 응답 파싱, 모델/하이브리드 파이프라인 통합 완료 | Codex |
| 1.0.2 | 2026-06-14 | 로컬 STT 런타임 가용성 게이트 추가: 모델 파일만으로 오프라인 STT가 활성화되지 않도록 Android/iOS `isRuntimeAvailable` 계약 등록 | Codex |
| 1.0.3 | 2026-06-14 | `whisper_ggml_plus` FFI plugin 직접 통합, 16kHz mono WAV 녹음 전환, MethodChannel stub 제거 | Codex |
| 1.0.4 | 2026-06-14 | 서비스 코어/FFI runtime/provider 분리, `freezed_annotation` 전이 lock 정합화, copied Flutter SDK 검증 추가 | Codex |
| 1.0.5 | 2026-06-14 | Flutter 전체 analyzer 게이트 정리, Android/iOS 모바일 CI workflow 및 로컬 검증 스크립트 추가 | Codex |
| 1.0.6 | 2026-06-14 | Android Gradle plugin 적용 누락 보강, iOS Podfile 15.0 고정, CI Gradle setup 추가 | Codex |
| 1.0.7 | 2026-06-14 | Android Gradle wrapper와 Flutter Gradle includeBuild 복원, Android CI SDK setup 추가, 로컬 검증 스크립트 native 옵션 분리, Flutter 3.44 권장 Gradle 8.14/AGP 8.11.1/Kotlin 2.2.20 고정 | Codex |
| 1.0.8 | 2026-06-14 | CocoaPods trunk 접근 재검증, Profile xcconfig Pods 연동, iOS Swift MethodChannel 컴파일 오류 수정, no-codesign iOS build 통과 | Codex |
| 1.0.9 | 2026-06-14 | 로컬 Android SDK 설치, compileSdk 36 전환, CI Android SDK 36/build-tools 설치 경로 반영, Android core library desugaring 활성화, Java/Kotlin JVM target 17 정합화, Android notification icon 리소스 정합화 | Codex |
| 1.0.10 | 2026-06-15 | release readiness에 `whisper_ggml_plus` FFI adapter/provider/Pod lock/smoke runner 게이트 추가 | Codex |

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| Backend STT | mlx-whisper (server), whisper-base (on-device) |
| On-Device | whisper.cpp NNACE 추론 (cross-platform) |
| Client | Flutter + Riverpod |
| Connectivity | 기존 ConnectivityService 재사용 |
| 플랫폼 | iOS 15+, macOS 12+, Android 10+ |

## 2. 가정 (Assumptions)

- SPEC-MOBILE-001 모바일 인프라가 완성되어 있다
- 기기에 200MB 이상 여유 공간이 있다 (모델 150MB + 오디오)
- Wi-Fi 환경에서 최초 모델 다운로드를 수행한다
- 오프라인 STT 정확도는 서버(large-v3)보다 낮다 (whisper-base 기준)
- 네트워크 복구 시 서버 STT로 자동 재처리한다

## 3. 요구사항 (Requirements)

### REQ-MOBILE-002-001: 모델 관리 [P0]

**EARS 형식**: 앱이 최초 실행되었을 때, 시스템은 whisper-base 모델 다운로드를 제공하고 SHA-256으로 무결성을 검증해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-001-01 | whisper-base 모델 다운로드 URL 관리 | P0 | [NEW] |
| REQ-MOBILE-002-001-02 | SHA-256 체크섬 검증 | P0 | [NEW] |
| REQ-MOBILE-002-001-03 | 모델 버전 관리 (업데이트 감지) | P1 | [NEW] |
| REQ-MOBILE-002-001-04 | 로컬 모델 경로 관리 (앱 문서 디렉토리) | P0 | [NEW] |

---

### REQ-MOBILE-002-002: 오프라인 STT 엔진 [P0-CRITICAL]

**EARS 형식**: 네트워크가 연결되지 않았을 때, 시스템은 on-device whisper-base로 음성을 텍스트로 변환해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-002-01 | whisper.cpp 추론 엔진 통합 | P0 | [NEW] |
| REQ-MOBILE-002-002-02 | 오디오 전처리 (16kHz mono WAV 변환) | P0 | [NEW] |
| REQ-MOBILE-002-002-03 | 한국어 언어 설정 고정 | P0 | [NEW] |
| REQ-MOBILE-002-002-04 | 세그먼트별 타임스탬프 출력 | P0 | [NEW] |
| REQ-MOBILE-002-002-05 | 추론 진행률 콜백 | P1 | [NEW] |

---

### REQ-MOBILE-002-003: 하이브리드 파이프라인 [P0-CRITICAL]

**EARS 형식**: 네트워크 상태에 따라 시스템은 오프라인 우선 처리 후 온라인 재처리를 수행해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-003-01 | 오프라인 시 로컬 STT 우선 실행 | P0 | [NEW] |
| REQ-MOBILE-002-003-02 | 로컬 결과를 임시 표시 (low-confidence 마크) | P0 | [NEW] |
| REQ-MOBILE-002-003-03 | 네트워크 복구 시 서버 STT 자동 재처리 | P0 | [NEW] |
| REQ-MOBILE-002-003-04 | 재처리 완료 시 결과 교체 (无缝 전환) | P0 | [NEW] |
| REQ-MOBILE-002-003-05 | ConnectivityProvider 기반 자동 분기 | P0 | [NEW] |

---

### REQ-MOBILE-002-004: 모델 다운로드 UX [P1]

**EARS 형형**: 사용자가 모델을 다운로드할 때, 시스템은 Wi-Fi 여부 확인 및 진행률을 표시해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-004-01 | Wi-Fi 연결 시에만 다운로드 권장 | P1 | [NEW] |
| REQ-MOBILE-002-004-02 | 진행률 UI (progress bar) | P1 | [NEW] |
| REQ-MOBILE-002-004-03 | 다운로드 실패 시 재시도 버튼 | P1 | [NEW] |
| REQ-MOBILE-002-004-04 | 모델 크기 표시 (~150MB) | P2 | [NEW] |

---

### REQ-MOBILE-002-005: 백엔드 재처리 지원 [P1]

**EARS 형식**: 오프라인 처리 결과가 있는 오디오가 업로드되었을 때, 시스템은 서버 STT로 재처리하고 결과를 교체해야 한다.

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-MOBILE-002-005-01 | POST /transcriptions에 local_result 메타데이터 전달 | P1 | [NEW] |
| REQ-MOBILE-002-005-02 | transcription_source 필드 (local/server/hybrid) | P1 | [NEW] |
| REQ-MOBILE-002-005-03 | 기존 파이프라인 호환성 유지 | P0 | [NEW] |

---

## 4. MVP 범위에서 제외

| 기능 | 제외 사유 | 향후 SPEC |
|------|---------|-----------|
| whisper-large on-device | 모델 크기 과대 (3GB+) | — |
| 플랫폼별 네이티브 가속 (CoreML/TFLite) | 복잡도 과대, 우선 호환성 | SPEC-MOBILE-003 |
| 오프라인 Diarization | 모델 크기 + 정확도 한계 | — |
| 로컬 결과 편집 UI | 우선 서버 결과로 대체 | — |

## 5. 기술 설계

```
┌─────────────────────────────────────────────────┐
│  Flutter Client                                  │
│  ┌─────────────────────────────────────────────┐ │
│  │ PipelineProvider (하이브리드 분기)           │ │
│  │  ├─ online → 서버 업로드 (기존 플로우)       │ │
│  │  └─ offline → LocalSttService 추론           │ │
│  │       └─ 네트워크 복구 시 서버 재처리 큐     │ │
│  ├─────────────────────────────────────────────┤ │
│  │ ModelManager (다운로드/검증/버전)            │ │
│  │ LocalSttService (whisper.cpp 추론)           │ │
│  │ ReprocessQueue (온라인 복구 시 재처리)       │ │
│  └─────────────────────────────────────────────┘ │
└────────────────┬────────────────────────────────┘
                 │ (온라인 시)
┌────────────────▼────────────────────────────────┐
│  Backend FastAPI                                 │
│  POST /transcriptions                            │
│  └─ local_result 메타데이터 옵션 처리            │
│  └─ transcription_source 필드 추가               │
└─────────────────────────────────────────────────┘
```

### 신규 파일

```
client/
├── lib/services/
│   ├── local_stt_service.dart        [NEW] on-device whisper 추론
│   ├── model_manager.dart            [NEW] 모델 다운로드/검증
│   └── reprocess_queue.dart          [NEW] 온라인 복구 시 재처리
├── lib/providers/
│   ├── hybrid_pipeline_provider.dart [NEW] 오프라인/온라인 분기
│   └── model_download_provider.dart  [NEW] 다운로드 진행률 상태
├── lib/models/
│   └── transcription_source.dart     [NEW] local/server/hybrid enum
├── lib/screens/
│   └── model_download_screen.dart    [NEW] 다운로드 UX

backend/
├── schemas/
│   └── transcription.py              [MODIFY] local_result 옵션 추가
```

## 6. 의존성 (Dependencies)

| 선행 SPEC | 내용 |
|-----------|------|
| SPEC-MOBILE-001 | 모바일 인프라 (녹음, ConnectivityService) |

**Client 의존성**:
```yaml
whisper_ggml_plus: ^1.5.2
```

## 7. 구현 현황

| 항목 | 상태 |
|------|------|
| on-device whisper | 완료: `whisper_ggml_plus` FFI plugin으로 whisper.cpp 런타임 직접 호출 |
| 하이브리드 파이프라인 | 완료 |
| 모델 다운로드 UX | 완료 |
| ConnectivityService | 기존 구현 존재 (재사용 가능) |
| 백엔드 재처리 | 완료 |

### 2026-06-14 프로덕션 보강

- `LocalSttService`는 `whisper_ggml_plus`의 `Whisper.transcribe()`를 직접 호출한다.
- `LocalSttService.isAvailable()`는 모델 파일 존재뿐 아니라 FFI runtime `getVersion()` 성공 여부까지 확인한다.
- `LocalSttService` 코어는 `LocalSttModelSource`와 `LocalSttRuntime` 계약만 의존한다. 실제 앱 provider는 `local_stt_provider.dart`에서 `SttModelManager`와 `WhisperGgmlLocalSttRuntime`을 연결한다.
- 녹음 파일은 core plugin 입력 조건에 맞춰 `.wav`, 16kHz, mono로 생성한다.
- Android/iOS 수동 MethodChannel stub은 제거했다. native whisper.cpp 링크는 Flutter FFI plugin packaging이 담당한다.
- `client/pubspec.lock`에는 `whisper_ggml_plus 1.5.2`와 전이 의존성 `freezed_annotation 3.1.0`이 반영되어 있다.
- `client/analysis_options.yaml`은 generated/build 산출물(`build/**`, `lib/dataconnect_generated/**`)을 analyzer 범위에서 제외하여 실제 앱/테스트 코드만 게이트한다.
- `.github/workflows/mobile.yml`은 PR/main push에서 Flutter `pub get`, `analyze`, `test`, Android debug APK build, iOS debug no-codesign build를 실행한다.
- `client/scripts/verify_mobile.sh`는 로컬에서 동일한 모바일 게이트(`pub get`, `analyze`, `test`, Android build, macOS에서 iOS no-codesign build)를 순차 실행한다.
- `client/android/app/build.gradle`은 `com.android.application`, `org.jetbrains.kotlin.android`, `dev.flutter.flutter-gradle-plugin`, `com.google.gms.google-services` 플러그인을 명시 적용한다.
- `client/android/settings.gradle`은 Flutter Gradle plugin composite build(`includeBuild("$flutterSdkPath/packages/flutter_tools/gradle")`)와 Google Services plugin version을 명시한다.
- `client/android/gradlew`, `client/android/gradlew.bat`, `client/android/gradle/wrapper/*`를 복원해 CI/로컬 Android build가 시스템 Gradle 설치에 의존하지 않는다.
- `client/macos/Podfile.lock`에는 `whisper_ggml_plus` macOS pod가 반영되어 macOS debug build에서도 whisper.cpp FFI plugin 링크 경로가 고정된다.

### 2026-06-14 재검증

- `cd client && ./scripts/verify_mobile.sh --native` -> `No issues found!`, `All tests passed!`, `local_stt_smoke: PASS`, `Built build/app/outputs/flutter-apk/app-debug.apk`, `Built build/ios/iphoneos/Runner.app`
- `cd client && flutter build macos --debug` -> `Built build/macos/Build/Products/Debug/voice_to_textnote.app`
- `cd client && flutter build web` -> `Built build/web`
- `client/android/settings.gradle`과 `client/android/build.gradle`은 Flutter 3.44 경고 기준에 맞춰 Android Gradle Plugin 8.11.1과 Kotlin Gradle Plugin 2.2.20을 사용한다.
- `client/android/app/build.gradle`은 release `minifyEnabled false`와 충돌하지 않도록 `shrinkResources false`를 명시한다.
- `client/android/app/build.gradle`은 Flutter plugin 요구사항에 맞춰 `compileSdk 36`을 사용한다.
- `client/android/app/build.gradle`은 `flutter_local_notifications` AAR metadata 요구사항에 맞춰 core library desugaring을 활성화한다.
- `client/android/app/build.gradle`은 Kotlin debug target과 일치하도록 Java source/target compatibility를 17로 설정한다.
- `client/ios/Podfile`은 SPEC 플랫폼 요구사항에 맞춰 `platform :ios, '15.0'`과 pod target `IPHONEOS_DEPLOYMENT_TARGET=15.0`을 고정한다.
- `client/ios/Flutter/Profile.xcconfig`는 `Pods-Runner.profile.xcconfig`와 `Generated.xcconfig`를 include하며, Runner Profile build configuration은 이 파일을 base configuration으로 사용한다.
- `client/ios/Runner/AppDelegate.swift`는 Swift `FlutterResult` 콜백 규약에 맞춰 MethodChannel no-op 응답을 `result(true)`로 반환한다.
- `.github/workflows/mobile.yml`은 Android job에서 Java 17, Android SDK 36/build-tools packages, Gradle setup을 명시해 CI build 경로를 확보한다.
- `client/scripts/verify_mobile.sh`는 기본 실행에서 Flutter pub/analyze/test/local STT smoke를 검증하고, `--native` 옵션에서는 Android SDK preflight 후 Android/iOS native build까지 실행한다.

### 2026-06-14 검증 증거

- `HOME=/private/tmp PUB_CACHE=/Users/ibkim/.pub-cache FLUTTER_SUPPRESS_ANALYTICS=true /private/tmp/flutter-codex.fn8k7a/bin/flutter --no-version-check pub get --offline` → `Got dependencies!`
- `HOME=/private/tmp PUB_CACHE=/Users/ibkim/.pub-cache FLUTTER_SUPPRESS_ANALYTICS=true /private/tmp/flutter-codex.fn8k7a/bin/dart --disable-analytics run tool/local_stt_smoke.dart` → `local_stt_smoke: PASS`
- `HOME=/private/tmp PUB_CACHE=/Users/ibkim/.pub-cache FLUTTER_SUPPRESS_ANALYTICS=true /private/tmp/flutter-codex.fn8k7a/bin/flutter --no-version-check analyze` → `No issues found!`
- `python - <<'PY' ... yaml.safe_load(...)` for `.github/workflows/mobile.yml` and `client/analysis_options.yaml` → `yaml ok`
- `bash -n client/scripts/verify_mobile.sh` → 통과
- `ruby -c client/ios/Podfile` → `Syntax OK`
- `git diff --check -- .github/workflows/mobile.yml client/analysis_options.yaml client/scripts/verify_mobile.sh client/lib client/test client/tool .moai/specs/SPEC-MOBILE-002/spec.md` → 통과
- `flutter test` → `All tests passed!`
- `flutter analyze` → `No issues found!`
- `cd client/android && ./gradlew help` → Flutter/AGP/Gradle 구성 평가 후 SDK preflight에서 중단: `SDK location not found. Define a valid SDK location with an ANDROID_HOME environment variable...`
- `cd client && ./scripts/verify_mobile.sh` → `All tests passed!`, `local_stt_smoke: PASS`, native build skip 안내 출력
- `cd client && ./scripts/verify_mobile.sh --native` → `No issues found!`, `All tests passed!`, `local_stt_smoke: PASS`, `✓ Built build/app/outputs/flutter-apk/app-debug.apk`, `✓ Built build/ios/iphoneos/Runner.app`
- `curl -I https://cdn.cocoapods.org/` → `HTTP/2 200`
- `cd client/ios && pod install` → `Pod installation complete! There are 5 dependencies from the Podfile and 5 total pods installed.`
- `flutter build ios --debug --no-codesign` → `✓ Built build/ios/iphoneos/Runner.app`
- `flutter config --android-sdk /Users/ibkim/Library/Android/sdk` → Android SDK path persisted in Flutter config
- `flutter doctor -v` → Android toolchain 인식: `Android SDK version 36.0.0`, `All Android licenses accepted.`
- `flutter build apk --debug` → `✓ Built build/app/outputs/flutter-apk/app-debug.apk`
- `flutter test test/services/local_stt_service_test.dart`는 이 sandbox에서 Flutter tester가 `127.0.0.1:0` server socket을 생성하지 못해 로딩 전 실패한다: `Failed to create server socket (OS Error: Operation not permitted, errno = 1)`. 동일 서비스 계약은 위 smoke runner로 검증했다.

### 2026-06-15 릴리스 readiness 보강

- `client/scripts/verify_release_readiness.py`는 `client/pubspec.yaml`과 `client/pubspec.lock`의 `whisper_ggml_plus 1.5.2` 고정을 확인한다.
- `local_stt_runtime_whisper.dart`가 `whisper_ggml_plus` FFI package를 import하고 `WhisperGgmlLocalSttRuntime`, `getVersion()`, `Whisper.transcribe()`, `TranscribeRequest`, `WhisperModel.base`, `WhisperVadMode.auto`를 유지하는지 확인한다.
- `local_stt_service.dart`가 모델 준비 상태와 FFI runtime availability를 둘 다 gate하고 한국어(`language: 'ko'`) 전사를 요청하는지 확인한다.
- `local_stt_provider.dart`가 `modelManagerProvider`와 `WhisperGgmlLocalSttRuntime`을 실제 앱 provider에 주입하는지 확인한다.
- `client/ios/Podfile.lock`과 `client/macos/Podfile.lock`의 `whisper_ggml_plus` native plugin symlink를 확인해 iOS/macOS native packaging 회귀를 릴리스 전에 차단한다.
- `client/tool/local_stt_smoke.dart`의 `local_stt_smoke: PASS` sentinel을 확인해 fake runtime 기반 서비스 계약 smoke runner가 유지되는지 확인한다.
- `python3 client/scripts/verify_release_readiness.py` → `release_readiness: 0 errors, 2 warnings`
- `cd client && dart run tool/local_stt_smoke.dart` → `local_stt_smoke: PASS`

## 8. 기술 제약사항

| 제약 | 설명 |
|------|------|
| 모델 크기 | whisper-base ~150MB (다운로드 필요) |
| 추론 속도 | 실시간의 1-3배 (기기 성능 의존) |
| 한국어 정확도 | whisper-base 기준 ~85% (large-v3 대비 낮음) |
| 메모리 | 추론 시 ~500MB 추가 사용 |
| 플랫폼 | iOS/macOS/Android 각각 네이티브 빌드 필요 |

---
*SPEC ID: SPEC-MOBILE-002*
*생성일: 2026-06-13*
*상태: completed*
