# Research: SPEC-MOBILE-005 — iOS 백그라운드 녹음 안정성 고도화

## 조사 일자
2026-06-13

## 조사 범위
1. 기존 코드베이스 분석 (SPEC-MOBILE-004 구현체)
2. Apple 공식 문서 (UIBackgroundModes, AVAudioSession)
3. Flutter `record` 패키지 소스 코드 및 공식 문서
4. 프로덕션 앱 패턴 (Expo, Element, Jitsi)

---

## 1. 기존 코드베이스 분석

### 현재 구현 상태

| 파일 | 상태 | 비고 |
|------|------|------|
| `background_recording_service.dart` | 부분 구현 | AudioSession 설정, interruption listener, flush timer 존재 |
| `recording_provider.dart | 기능 동작 | 상태 머신 (idle→recording→paused→stopped) |
| `recording_recovery_service.dart` | 부분 구현 | 경로+타임스탬프 저장, 무결성 검사 부재 |
| `AppDelegate.swift` | **사실상 비어있음** | MethodChannel 핸들러 zero (16줄) |
| `Info.plist` | 적절함 | UIBackgroundModes: [audio, remote-notification] |
| `MainActivity.kt` + `RecordingService.kt` | 완전 구현 | Android Foreground Service (참조 모델) |

### 13개 갭 식별

| # | 갭 | 심각도 | iOS 고유 |
|---|-----|--------|---------|
| G1 | iOS 네이티브 MethodChannel 핸들러 부재 | CRITICAL | Yes |
| G2 | `UIApplication.beginBackgroundTask` 미사용 | CRITICAL | Yes |
| G3 | 인터럽션 핸들러가 로그만 출력 (pause/resume 미호출) | HIGH | Yes |
| G4 | `devicesChangedEventStream` 미구독 (route change) | HIGH | Yes |
| G5 | 인터럽션 `event.type` (.shouldResume) 미확인 | MEDIUM | Yes |
| G6 | `RecordConfig` 최소값만 지정 (sampleRate 등 누락) | HIGH | Both |
| G7 | Lifecycle `paused`/`inactive` 미처리 | HIGH | Both |
| G8 | AudioSession 옵션 누락 (A2DP, duckOthers 등) | MEDIUM | Yes |
| G9 | 복구 시 파일 무결성 검사 부재 | MEDIUM | Both |
| G10 | 권한 검사 경로 이원화 | LOW | Both |
| G11 | catch 블록 에러 무음 삼킴 | MEDIUM | Both |
| G12 | iOS 백그라운드 녹음 표시기 부재 | LOW | Yes |
| G13 | Flush timer가 Flutter 엔진 생존에 의존 | HIGH | Yes |

---

## 2. Apple 공식 문서 핵심 발견

### UIBackgroundModes: audio
- **녹음+재생 모두 커버** — "plays audible content **or records audio** while in the background"
- audio mode 앱은 적극적으로 오디오 I/O 하는 한 **suspend 되지 않음**
- 30초 제한은 `beginBackgroundTask`에만 해당 — audio mode는 **무제한**
- 단, 녹음/재생이 중지되면 즉시 suspend

### AVAudioSession 권장사항
- `.playAndRecord`가 `.record`보다 권장됨 (Apple 공식)
- `.record`는 시스템 출력을 모두 mute — 너무 제한적
- 화면 잠금으로 recording이 중지되지 않음 (`.playAndRecord`, `.record` 모두)
- 세션 비활성화 시 `notifyOthersOnDeactivation` 처리 권장

### 인터럽션 처리 패턴
1. `AVAudioSession.interruptionNotification` 관찰
2. `.began`: 녹음 pause, 세션은 비활성화하지 않음
3. `.ended`: `.shouldResume` 확인 → 세션 재활성화 → 녹음 resume

### iOS가 백그라운드 앱을 kill하는 조건
1. 사용자 강제 종료 (swipe up)
2. 오디오 중지 → 즉시 suspend
3. CPU 80%+ 60초 → `EXC_RESOURCE` kill
4. 백그라운드 태스크 누수 → `0x8badf00d`
5. 메모리 압박 → jetsam kill

---

## 3. Flutter `record` 패키지 분석

### 버전: ^6.0.0 (SHA: 8b74fa0)

### AudioInterruptionMode enum
```swift
case none = 0        // 인터럽션 처리 안 함 — 녹음이 kill될 수 있음
case pause = 1       // 인터럽션 시 pause, 자동 resume 안 함 (기본값)
case pauseResume = 2 // pause + 자동 resume (mixWithOthers 필수)
```

### 핵심 발견: Issue #542 (백그라운드 resume 실패)
- **원인**: 백그라운드에서 세션이 deactivate되면 `setActive(true)`가 `-560557684` 에러로 실패
- **워크어라운드**: `.mixWithOthers` 포함 시 일부 해결
- **한계**: iOS 18.x에서 여전히 실패 보고 존재 — **알려진 미해결 제약**

### 카테고리 하드코딩
```swift
// record_ios/RecorderSessionExtension.swift L46
try session.setCategory(.playAndRecord, options: options)
```
→ `.playAndRecord`로 고정됨, Dart에서 category 자체는 변경 불가 (options만 가능)

### 공식 권장사항
> Background recording은 플러그인 자체에서 지원하지 않음. `UIBackgroundModes: audio` + `flutter_foreground_task` 조합 권장.
> 단, iOS에서는 `flutter_foreground_task`가 불필요 — `UIBackgroundModes: audio`가 유일한 올바른 메커니즘.

---

## 4. 프로덕션 앱 패턴

### Expo Audio (expo/expo)
- `AVAudioSession.interruptionNotification` 관찰
- `.began` → `handleInterruptionBegan()`, `.ended` → 옵션 체크 후 resume

### Element (element-hq/element-ios)
- VoiceMessageAudioRecorder에서 동일 패턴 구현
- `wasRecordingBeforeInterruption` 플래그로 상태 추적

### 핵심 교훈
1. 네이티브 Swift 코드에서 인터럽션 처리가 필요 (Dart만으로는 한계)
2. `routeChangeNotification` 관찰로 이어폰/블루투스 연결 변화 대응
3. 백그라운드 resume 실패는 **사용자 알림 + 부분 녹음 보존**으로 대응

---

## 5. 결론: SPEC 범위 권장사항

### 구현 권장 (P0/P1)
- G1: iOS 네이티브 MethodChannel 핸들러 (AppDelegate.swift)
- G3+G5: 인터럽션 실제 pause/resume + shouldResume 확인
- G4: Route change 처리 (devicesChangedEventStream)
- G6: RecordConfig 고급화
- G7: Lifecycle handling 확장
- G8: AudioSession 옵션 보완
- G11: 에러 핸들링 개선

### 문서화만 (P2 — iOS 제약)
- G2+G13: `beginBackgroundTask`는 30초 제한으로 audio mode에 불필요하나, crash 방지용 보조 수단으로 검토
- G12: iOS 백그라운드 녹음 표시기 (Now Playing 또는 위젯)
- Issue #542: 백그라운드 인터럔션 resume 실패 — 사용자 알림 + 부분 녹음 보존으로 대응
