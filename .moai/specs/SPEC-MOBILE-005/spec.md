---
id: SPEC-MOBILE-005
version: "1.0.0"
status: draft
created: "2026-06-13"
updated: "2026-06-13"
author: sisyphus
priority: high
issue_number: TBD
depends_on: SPEC-MOBILE-004
---

# SPEC-MOBILE-005: iOS 백그라운드 녹음 안정성 고도화

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 초안 작성 — SPEC-MOBILE-004 후속, iOS 백그라운드 녹음 13개 갭 해결 | sisyphus |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 프레임워크 | Flutter 3.24+ / Dart 3.5+ |
| 상태관리 | Riverpod 2.6+ (flutter_riverpod) |
| 오디오 녹음 | record ^6.0.0 + audio_session ^0.1.21 |
| iOS 네이티브 | Swift 5.9+, UIKit, AVFAudio |
| 권한 관리 | permission_handler ^11.3.0 |
| 로컬 저장소 | shared_preferences ^2.3+ |
| 대상 플랫폼 | iOS 15+ (Android는 SPEC-MOBILE-004에서 이미 완료) |
| 개발 환경 | macOS (M4 Mac mini), Xcode 15+ |
| 개발 방법론 | TDD (Red-Green-Refactor) |
| 선행 SPEC | SPEC-MOBILE-004 (completed) |

---

## 2. 가정 (Assumptions)

- SPEC-MOBILE-004의 모든 구현이 완료된 상태이다 (Push 알림, 권한 통합, 백그라운드 녹음 복원, Android flush).
- Android `RecordingService.kt` + `MainActivity.kt` MethodChannel 패턴을 iOS의 참조 모델로 사용한다.
- `record` 패키지 ^6.0.0의 `AudioInterruptionMode` enum 및 `IosRecordConfig`를 활용 가능하다.
- iOS 15+를 타겟으로 하며, iOS 18.x의 알려진 백그라운드 resume 실패 제약 (Issue #542)은 사용자 알림으로 대응한다.
- Apple Developer 계정이 사용 가능하다 (실기기 테스트용).
- 기존 백엔드 테스트와 Flutter 테스트가 통과하는 상태를 유지해야 한다.

---

## 3. 요구사항 (Requirements)

### REQ-MOBILE-005-001: iOS 네이티브 녹음 서비스 구현 [P0-CRITICAL]

**EARS 형식**: 사용자가 iOS 기기에서 백그라운드 녹음을 시작했을 때, 시스템은 Swift 네이티브 MethodChannel 핸들러를 통해 백그라운드 오디오 세션을 보호하고, 시스템에 의해 앱이 일시 정지되더라도 녹음이 중단되지 않도록 보장해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-001-01 | `AppDelegate.swift`에 `FlutterMethodChannel("com.voicetextnote.app/recording")` 핸들러를 구현한다 — `startBackgroundTask`, `stopBackgroundTask`, `flushRecording` 3개 메서드 | P0 | [NEW] |
| REQ-001-02 | `startBackgroundTask` 호출 시 `UIApplication.shared.beginBackgroundTask(withName:)`를 실행하여 OS에 백그라운드 실행 권한을 요청한다 (crash 방지 보조 수단) | P0 | [NEW] |
| REQ-001-03 | `stopBackgroundTask` 호출 시 `endBackgroundTask`로 백그라운드 태스크를 해제한다 | P0 | [NEW] |
| REQ-001-04 | `flushRecording`은 현재 오디오 세션 활성 상태를 확인하고 필요시 `setActive(true)`를 호출한다 | P1 | [NEW] |
| REQ-001-05 | Dart `BackgroundRecordingService._methodChannel.invokeMethod('flushRecording')` 호출이 iOS에서 `MissingPluginException` 없이 정상 응답하도록 한다 | P0 | [NEW] |
| REQ-001-06 | Android `MainActivity.kt`와 iOS `AppDelegate.swift`의 MethodChannel 인터페이스 시그니처를 통일한다 | P1 | [NEW] |

**검증**: 단위 테스트로 MethodChannel 핸들러 등록 여부 검증. 실기기 테스트로 백그라운드→포그라운드 전환 시 녹음 연속성 확인.

**참조**: Android `MainActivity.kt:16-33`, `RecordingService.kt`를 참조 모델로 사용.

---

### REQ-MOBILE-005-002: 오디오 세션 인터럽션 고도화 [P0-CRITICAL]

**EARS 형식**: 전화, 알람, Siri 등의 시스템 인터럽션이 발생했을 때, 시스템은 녹음을 자동으로 일시정지하고 RecordingProvider 상태를 업데이트해야 하며, 인터럽션 종료 후 `.shouldResume` 플래그가 설정된 경우에만 녹음을 재개해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-002-01 | `_handleInterruptionBegin()`에서 `_recorder!.pause()`를 실제로 호출하고 `RecordingProvider` 상태를 `paused`로 업데이트한다 (현재는 로그만 출력) | P0 | [NEW] |
| REQ-002-02 | `_handleInterruptionEnd()`에서 `audio_session`의 `interruptionEvent` type이 `.shouldResume`인 경우에만 `_recorder!.resume()`을 호출한다 | P0 | [NEW] |
| REQ-002-03 | 인터럽션 종료 시 `.shouldNotResume`이면 사용자에게 "녹음이 일시정지되었습니다" 알림을 표시하고 수동 resume를 유도한다 | P1 | [NEW] |
| REQ-002-04 | `RecordConfig`에 `audioInterruption: AudioInterruptionMode.pauseResume`를 설정하여 `record` 패키지의 네이티브 인터럽션 처리를 활성화한다 | P0 | [NEW] |
| REQ-002-05 | `iosConfig.categoryOptions`에 `IosAudioCategoryOption.mixWithOthers`를 포함한다 (pauseResume 모드 필수 조건) | P0 | [NEW] |

**검증**: 통합 테스트로 인터럽션 begin/end 시 상태 전이 검증. 실기기 테스트로 전화 수신/종료 시나리오 확인.

**주의**: iOS 18.x 백그라운드에서 인터럽션 종료 후 resume이 실패할 수 있음 (record 패키지 Issue #542). 이 경우 부분 녹음 파일 보존 + 사용자 알림으로 대응 (REQ-004-03 참조).

---

### REQ-MOBILE-005-003: 오디오 라우트 변경 처리 [P1]

**EARS 형식**: 블루투스 이어폰 연결/해제, 유선 이어폰 플러그/언플러그 등 오디오 라우트 변경이 발생했을 때, 시스템은 녹음을 일시정지하고 사용자에게 라우트 변경을 알림 후 새 라우트로 수동 재개를 유도해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-003-01 | `audio_session`의 `devicesChangedEventStream`을 구독하여 오디오 기기 연결/해제를 감지한다 | P1 | [NEW] |
| REQ-003-02 | 라우트 변경 감지 시 `_recorder!.pause()`를 호출하고 `RecordingProvider` 상태를 `paused`로 업데이트한다 | P1 | [NEW] |
| REQ-003-03 | 라우트 변경 시 사용자에게 스낵바/알림으로 "오디오 기기가 변경되었습니다"를 표시한다 | P2 | [NEW] |
| REQ-003-04 | iOS 네이티브 `AVAudioSession.routeChangeNotification`을 AppDelegate에서 관찰하여 Dart에 MethodChannel 이벤트로 전달한다 | P2 | [NEW] |

**검증**: 통합 테스트로 `devicesChangedEventStream` 구독 검증. 실기기 테스트로 Bluetooth 연결/해제 시나리오 확인.

---

### REQ-MOBILE-005-004: RecordConfig 및 AudioSession 구성 고도화 [P1]

**EARS 형식**: 회의 녹음 시작 시, 시스템은 고품질 음성 녹음을 위한 명시적 오디오 설정(샘플레이트, 채널 수, 비트레이트, 음향 처리)을 적용하고, iOS AudioSession 카테고리 옵션을 최적화해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-004-01 | `RecordConfig`에 명시적 `sampleRate: 16000`, `numChannels: 1`, `bitRate: 64000`을 설정한다 (회의 음성 최적화) | P1 | [NEW] |
| REQ-004-02 | `RecordConfig`에 `autoGain: true`, `echoCancel: true`, `noiseSuppress: true`를 설정한다 (iOS voice processing 활성화) | P1 | [NEW] |
| REQ-004-03 | `iosConfig.categoryOptions`에 다음 옵션을 포함한다: `allowBluetooth`, `allowBluetoothA2DP`, `duckOthers`, `defaultToSpeaker`, `mixWithOthers` | P1 | [NEW] |
| REQ-004-04 | `AudioSession` 설정에서 `avAudioSessionMode`를 `.spokenAudio`로 변경한다 (회의 음성에 최적화된 모드) | P2 | [NEW] |
| REQ-004-05 | 인터럽션 종료 후 resume 실패 시 (Issue #542 시나리오), 부분 녹음 파일을 보존하고 사용자에게 "네트워크/기기 문제로 녹음이 중단되었습니다. 지금까지의 녹음을 저장합니다" 알림을 표시한다 | P1 | [NEW] |

**검증**: 단위 테스트로 RecordConfig 값 검증. 음질 비교 테스트 (이전 vs 개선 후 녹음 파일).

---

### REQ-MOBILE-005-005: 앱 라이프사이클 녹음 보호 [P1]

**EARS 형식**: 앱이 백그라운드로 전환되거나 비활성화될 때, 시스템은 현재 녹음 상태를 영속 저장소에 저장하고, 앱 재개 시 녹음 상태를 복원해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-005-01 | `main.dart`의 `didChangeAppLifecycleState`에서 `paused` 및 `inactive` 상태를 처리한다 (현재는 `resumed`만 처리) | P1 | [NEW] |
| REQ-005-02 | `paused` 상태 진입 시 `RecordingRecoveryService`에 현재 녹음 경로, 경과 시간, 상태를 업데이트한다 | P1 | [NEW] |
| REQ-005-03 | `inactive` 상태 진입 시 (제어센터, 알림 센터) 녹음을 일시정지하지 않고 세션 유지 상태로 둔다 | P2 | [NEW] |
| REQ-005-04 | `resumed` 상태 복귀 시 미완료 녹음이 있으면 파일 무결성(크기 > 0, 존재 여부)을 검증 후 복원 다이얼로그를 표시한다 | P1 | [NEW] |
| REQ-005-05 | `RecordingScreen`에 `WidgetsBindingObserver`를 추가하여 화면 단위의 라이프사이클 반응을 구현한다 | P2 | [NEW] |

**검증**: 통합 테스트로 lifecycle 상태 전이 시 SharedPreferences 업데이트 검증. 실기기 테스트로 홈 버튼/앱 전환 시나리오 확인.

---

### REQ-MOBILE-005-006: 에러 핸들링 및 관측성 개선 [P2]

**EARS 형식**: 녹음 관련 예외가 발생했을 때, 시스템은 에러를 로그에 기록하고 사용자에게 의미 있는 피드백을 제공해야 한다.

**상세 요구사항**:

| ID | 요구사항 | 우선순위 | 상태 |
|----|---------|---------|------|
| REQ-006-01 | `pauseRecording()` 및 `resumeRecording()`의 catch 블록에서 에러를 `logger`로 출력하고 `RecordingProvider`에 에러 상태를 전파한다 (현재는 무음 삼킴) | P2 | [NEW] |
| REQ-006-02 | `_methodChannel.invokeMethod` 실패 시 플랫폼(iOS/Android)을 구분하여 로그에 기록한다 | P2 | [NEW] |
| REQ-006-03 | 권한 검사 경로를 `PermissionService` 단일 경로로 통일한다 (`record.hasPermission()` 중복 호출 제거) | P2 | [NEW] |

**검증**: 단위 테스트로 에러 로깅 검증. 통합 테스트로 의도적 실패 시나리오 확인.

---

## 4. MVP 범위에서 제외

| 기능 | 제외 사유 | 향후 SPEC |
|------|----------|----------|
| `flutter_foreground_task` 도입 | iOS에서는 `UIBackgroundModes: audio`가 유일한 올바른 메커니즘, 불필요 | - |
| Now Playing 위젯 (iOS 백그라운드 표시기) | UX 개선 사항, 핵심 안정성과 분리 | SPEC-MOBILE-006 |
| 백그라운드 자동 업로드 (workmanager) | P2 후순위, 네트워크/배터리 영향 큼 | 별도 검토 |
| iOS Widget (Lock Screen) | UX 개선 단계, 별도 디자인 필요 | SPEC-MOBILE-007 |
| Siri 음성 명령 | 핵심 기능 아님 | SPEC-MOBILE-008 |

---

## 5. 기술 설계

### 5.1 iOS 네이티브 아키텍처

```
AppDelegate.swift (현재: 16줄 → 목표: 완전한 MethodChannel 핸들러)
├── FlutterMethodChannel("com.voicetextnote.app/recording")
│   ├── startBackgroundTask → UIApplication.shared.beginBackgroundTask()
│   ├── stopBackgroundTask  → task.endBackgroundTask()
│   └── flushRecording      → AVAudioSession.setActive(true)
├── AVAudioSession.interruptionNotification 관찰
│   ├── .began  → Dart에 이벤트 전달 (MethodChannel.invokeMethod)
│   └── .ended  → shouldResume 체크 → Dart에 이벤트 전달
└── AVAudioSession.routeChangeNotification 관찰
    └── route 변경 → Dart에 이벤트 전달
```

### 5.2 인터럽션 처리 흐름

```
[현재 — 로그만]
  interruption begin → print("녹음이 일시정지됨") → 아무 동작 안 함
  interruption end   → session.setActive(true) → recorder.resume() 안 함

[목표 — 완전한 상태 머신]
  interruption begin →
    1. _recorder.pause()
    2. RecordingProvider.status = paused
    3. RecoveryService.updateElapsed()
    4. UI: "일시정지됨" 표시

  interruption end (shouldResume=true) →
    1. session.setActive(true, notifyOthersOnDeactivation: false)
    2. _recorder.resume()
    3. RecordingProvider.status = recording
    4. UI: "녹음 재개" 표시

  interruption end (shouldResume=false) →
    1. RecordingProvider.status = paused
    2. UI: "녹음이 중단되었습니다. 수동으로 재개하세요"
    3. 부분 녹음 파일 보존

  resume 실패 (Issue #542 시나리오) →
    1. 파일 보존 확인
    2. UI: "기기 문제로 녹음이 중단되었습니다. 지금까지의 녹음을 저장합니다"
    3. stopRecording() → 파일 업로드 가능 상태로 전환
```

### 5.3 RecordConfig 고도화

```dart
// 현재
const RecordConfig(encoder: AudioEncoder.aacLc)

// 목표
const RecordConfig(
  encoder: AudioEncoder.aacLc,
  sampleRate: 16000,       // 회의 음성 최적화
  numChannels: 1,           // 모노
  bitRate: 64000,           // 음성 품질/크기 균형
  autoGain: true,           // iOS voice processing
  echoCancel: true,         // 스피커폰 에코 제거
  noiseSuppress: true,      // 배경 소음 억제
  audioInterruption: AudioInterruptionMode.pauseResume,  // 네이티브 인터럽션 처리
  iosConfig: IosRecordConfig(
    categoryOptions: [
      IosAudioCategoryOption.allowBluetooth,
      IosAudioCategoryOption.allowBluetoothA2DP,   // iOS 14+ 고품질 BT
      IosAudioCategoryOption.duckOthers,           // 다른 오디오 볼륨 낮춤
      IosAudioCategoryOption.defaultToSpeaker,     // 스피커 폴백
      IosAudioCategoryOption.mixWithOthers,        // pauseResume 필수 조건
    ],
  ),
)
```

### 5.4 디렉토리 구조 변경

```
client/
├── lib/
│   ├── services/
│   │   ├── background_recording_service.dart  # [MODIFY] 인터럽션 실제 pause/resume, route change 구독
│   │   ├── recording_recovery_service.dart    # [MODIFY] 파일 무결성 검사 추가
│   │   └── permission_service.dart            # [MODIFY] 권한 검사 경로 통일
│   ├── providers/
│   │   └── recording_provider.dart            # [MODIFY] 인터럽션 상태 전이 추가
│   ├── screens/
│   │   └── recording_screen.dart              # [MODIFY] WidgetsBindingObserver 추가
│   └── main.dart                              # [MODIFY] paused/inactive 라이프사이클 처리
├── ios/
│   └── Runner/
│       ├── AppDelegate.swift                  # [REWRITE] MethodChannel + AVAudioSession 관찰
│       └── Info.plist                         # [VERIFY] UIBackgroundModes 유지
└── android/                                   # [NO CHANGE] 이미 완료
```

---

## 6. 의존성 (Dependencies)

### 선행 SPEC

| SPEC | 상태 | 관계 |
|------|------|------|
| SPEC-MOBILE-004 | completed | 백그라운드 녹음 복원, 권한 통합, Push 알림 기반 |
| SPEC-MOBILE-001 | completed | Phase A/B/C 인프라 |

### 의존성 변경사항

**추가 의존성 없음** — 기존 패키지로 모든 요구사항 충족 가능:
```yaml
# pubspec.yaml (변경 없음)
dependencies:
  record: ^6.0.0              # AudioInterruptionMode, IosRecordConfig 활용
  audio_session: ^0.1.21      # devicesChangedEventStream 활용
  permission_handler: ^11.3.0
  shared_preferences: ^2.3+
```

### 외부 서비스

| 서비스 | 용도 | 설정 필요 |
|--------|------|----------|
| Apple Developer | 실기기 테스트, 백그라운드 모드 검증 | 기존 계정 사용 |

---

## 7. 구현 현황

**버전**: v1.0.0
**진행 상태**: draft (SPEC 생성 완료, 구현 대기)

### 갭 매트릭스 (13개 갭 → 요구사항 매핑)

| 갭 | 심각도 | 매핑된 REQ | 비고 |
|----|--------|-----------|------|
| G1 | CRITICAL | REQ-001 | iOS MethodChannel 구현 |
| G2 | CRITICAL | REQ-001 | beginBackgroundTask |
| G3 | HIGH | REQ-002 | 인터럽션 실제 pause/resume |
| G4 | HIGH | REQ-003 | route change 처리 |
| G5 | MEDIUM | REQ-002 | shouldResume 확인 |
| G6 | HIGH | REQ-004 | RecordConfig 고급화 |
| G7 | HIGH | REQ-005 | Lifecycle 처리 확장 |
| G8 | MEDIUM | REQ-004 | AudioSession 옵션 보완 |
| G9 | MEDIUM | REQ-005 | 파일 무결성 검사 |
| G10 | LOW | REQ-006 | 권한 경로 통일 |
| G11 | MEDIUM | REQ-006 | 에러 핸들링 개선 |
| G12 | LOW | 제외 | UX 개선 (별도 SPEC) |
| G13 | HIGH | REQ-001+005 | 네이티브 보조 + Lifecycle 보호 |

---

## 8. 기술 제약사항

| 제약 | 설명 | 대응 |
|------|------|------|
| iOS 18.x 백그라운드 resume 실패 | `record` 패키지 Issue #542 — 백그라운드에서 인터럽션 종료 후 세션 재활성화 실패 | REQ-004-05: 부분 녹음 보존 + 사용자 알림 |
| iOS 시뮬레이터 한계 | 백그라운드 녹음, 인터럽션 시뮬레이션 불가 | 실기기 테스트 필수 (REQ-001/002/003 검증용) |
| audio_session 플러그인 의존 | Dart 단에서 AVAudioSession 제어가 플러그인 API에 제한됨 | 네이티브 AppDelegate에서 보완 (REQ-001) |
| `beginBackgroundTask` 30초 제한 | 오디오 mode 앱에는 사실상 불필요 (audio mode가 무제한) | crash 방지 보조 수단으로만 사용, 주 메커니즘은 UIBackgroundModes: audio |
| CPU 모니터 | 백그라운드에서 80% CPU 60초 시 kill | 녹음 중 무거운 연산 회피 |

---

## 9. 허용 기준 (Acceptance Criteria)

### 자동화 검증 (TDD)

| AC ID | 요구사항 | 검증 방법 |
|-------|---------|----------|
| AC-001 | AppDelegate.swift에 3개 MethodChannel 핸들러가 등록되어 있다 | 단위 테스트 (Swift) |
| AC-002 | 인터럽션 begin 시 `_recorder.pause()`가 호출된다 | 통합 테스트 (mock) |
| AC-003 | 인터럽션 end + shouldResume 시 `_recorder.resume()`이 호출된다 | 통합 테스트 (mock) |
| AC-004 | 인터럽션 end + shouldNotResume 시 사용자 알림이 표시된다 | 위젯 테스트 |
| AC-005 | `devicesChangedEventStream`이 구독되어 있다 | 단위 테스트 |
| AC-006 | RecordConfig에 sampleRate=16000, numChannels=1, bitRate=64000이 설정되어 있다 | 단위 테스트 |
| AC-007 | RecordConfig에 autoGain, echoCancel, noiseSuppress가 true로 설정되어 있다 | 단위 테스트 |
| AC-008 | iosConfig.categoryOptions에 5개 옵션이 포함되어 있다 | 단위 테스트 |
| AC-009 | `didChangeAppLifecycleState`에서 paused 상태를 처리한다 | 통합 테스트 |
| AC-010 | 복구 시 파일 크기 > 0 검증을 수행한다 | 단위 테스트 |
| AC-011 | pause/resume 실패 시 에러가 로그에 기록된다 | 단위 테스트 |
| AC-012 | 기존 모든 백엔드 테스트가 통과한다 | pytest 회귀 |
| AC-013 | 기존 모든 Flutter 테스트가 통과한다 | flutter test 회귀 |
| AC-014 | dart analyze 0 issues (신규/수정 파일) | dart analyze |
| AC-015 | 코드 커버리지 85%+ (신규/수정 파일) | flutter test --coverage |

### 실기기 검증 (수동)

| AC ID | 요구사항 | 검증 방법 |
|-------|---------|----------|
| AC-M01 | 백그라운드 전환 후 녹음이 연속된다 | 홈 버튼 → 30초 대기 → 복귀 → 파일 확인 |
| AC-M02 | 화면 잠금 후 녹음이 연속된다 | 화면 끄기 → 30초 대기 → 잠금 해제 → 파일 확인 |
| AC-M03 | 전화 수신 시 녹음이 일시정지된다 | 녹음 중 전화 수신 → 상태 확인 |
| AC-M04 | 전화 종료 후 shouldResume 시 녹음이 재개된다 | 전화 종료 → 상태 확인 |
| AC-M05 | 블루투스 해제 시 녹음이 일시정지된다 | 녹음 중 BT 해제 → 상태 확인 |
| AC-M06 | 앱 강제 종료 후 재시작 시 복원 다이얼로그가 표시된다 | 강제 종료 → 재시작 → 다이얼로그 확인 |

---

## 10. 위험 평가

| 위험 | 확률 | 영향 | 완화책 |
|------|------|------|--------|
| iOS 18.x 백그라운드 resume 실패 (Issue #542) | 높음 | 중간 | 부분 녹음 보존 + 사용자 알림 (REQ-004-05) |
| AppDelegate 변경 시 기존 Flutter 플러그인 호환성 | 중간 | 높음 | GeneratedPluginRegistrant 유지, 점진적 추가 |
| audio_session + record 패키지 인터럽션 처리 충돌 | 중간 | 중간 | 한쪽에서만 처리하도록 단일화 (REQ-002-04로 record 패키지 처리 위임) |
| AudioInterruptionMode.pauseResume + mixWithOthers 필수 | 확실 | 낮음 | REQ-002-05에서 명시적 설정 |

---

*SPEC ID: SPEC-MOBILE-005*
*생성일: 2026-06-13*
*상태: draft*
