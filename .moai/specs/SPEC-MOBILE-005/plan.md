# Implementation Plan: SPEC-MOBILE-005

## SPEC ID
SPEC-MOBILE-005: iOS 백그라운드 녹음 안정성 고도화

## 브랜치
`feature/SPEC-MOBILE-005` (from `main`)

## 구현 순서 (의존성 기반)

### Batch 1: iOS 네이티브 기반 (REQ-001) [P0-CRITICAL]
**의존성**: 없음 (독립적)
**파일**:
- `client/ios/Runner/AppDelegate.swift` — MethodChannel 핸들러 3개 + AVAudioSession 관찰
- `client/lib/services/background_recording_service.dart` — MethodChannel 응답 검증

**TDD 사이클**:
1. RED: AppDelegate MethodChannel 등록 테스트 (Swift 단위 테스트)
2. GREEN: startBackgroundTask/stopBackgroundTask/flushRecording 구현
3. REFACTOR: Android와 인터페이스 통일

### Batch 2: 오디오 세션 인터럽션 + Route Change (REQ-002, REQ-003) [P0/P1]
**의존성**: Batch 1 (MethodChannel 이벤트 전달)
**파일**:
- `client/lib/services/background_recording_service.dart` — 인터럽션 실제 pause/resume, route change 구독
- `client/lib/providers/recording_provider.dart` — 인터럽션 상태 전이

**TDD 사이클**:
1. RED: 인터럽션 begin → pause 호출 테스트, end + shouldResume → resume 호출 테스트
2. GREEN: _handleInterruptionBegin/End 구현, devicesChangedEventStream 구독
3. REFACTOR: 에러 핸들링 개선 (catch 블록 로깅)

### Batch 3: RecordConfig + AudioSession 고도화 (REQ-004) [P1]
**의존성**: Batch 2 (audioInterruption 모드와 연동)
**파일**:
- `client/lib/services/background_recording_service.dart` — RecordConfig 확장
- `client/lib/services/background_recording_service.dart` — AudioSession 옵션 보완

**TDD 사이클**:
1. RED: RecordConfig 값 검증 테스트 (sampleRate, channels, bitRate, AGC/AEC/NS)
2. GREEN: 명시적 설정 적용
3. REFACTOR: 상수 추출 (녹음 설정값)

### Batch 4: 라이프사이클 + 복구 + 에러 핸들링 (REQ-005, REQ-006) [P1/P2]
**의존성**: Batch 2 (상태 전이), Batch 3 (복구 검증)
**파일**:
- `client/lib/main.dart` — paused/inactive 처리
- `client/lib/screens/recording_screen.dart` — WidgetsBindingObserver
- `client/lib/services/recording_recovery_service.dart` — 파일 무결성 검사
- `client/lib/services/permission_service.dart` — 권한 경로 통일

**TDD 사이클**:
1. RED: lifecycle paused → SharedPreferences 업데이트 테스트
2. GREEN: didChangeAppLifecycleState 확장, 파일 무결성 검사
3. REFACTOR: 에러 로깅 표준화

## 병렬 실행 기회

| 그룹 | 배치 | 병렬 가능? | 비고 |
|------|------|-----------|------|
| A | Batch 1 | 독립 | iOS 네이티브 전용 |
| B | Batch 2 | Batch 1 후 | Dart 서비스 레이어 |
| C | Batch 3 | Batch 2와 병렬 가능 | RecordConfig는 독립적 |
| D | Batch 4 | Batch 2+3 후 | Lifecycle은 전체와 연동 |

## 예상 파일 변경

| 파일 | 변경 유형 | 배치 |
|------|----------|------|
| `client/ios/Runner/AppDelegate.swift` | REWRITE | 1 |
| `client/lib/services/background_recording_service.dart` | MODIFY (major) | 1, 2, 3 |
| `client/lib/providers/recording_provider.dart` | MODIFY | 2 |
| `client/lib/main.dart` | MODIFY | 4 |
| `client/lib/screens/recording_screen.dart` | MODIFY | 4 |
| `client/lib/services/recording_recovery_service.dart` | MODIFY | 4 |
| `client/lib/services/permission_service.dart` | MODIFY | 4 |
| `client/test/...` | NEW | 1-4 |

## 위험 완화

| 위험 | 배치 | 완화 |
|------|------|------|
| AppDelegate 변경 → 플러그인 호환성 | 1 | GeneratedPluginRegistrant 유지 |
| 인터럽션 처리 이중화 (audio_session vs record) | 2 | record 패키지에 위임 (AudioInterruptionMode.pauseResume) |
| iOS 18.x 백그라운드 resume 실패 | 2 | 부분 녹음 보존 + 알림 (AC-M04 대안) |

## 예상 소요
- Batch 1: ~2시간 (Swift 네이티브)
- Batch 2: ~3시간 (인터럽션 상태 머신)
- Batch 3: ~1시간 (RecordConfig)
- Batch 4: ~2시간 (Lifecycle + 복구)
- 총: ~8시간
