# SPEC-MOBILE-005 Acceptance Criteria

## 검증 방법
본 문서는 spec.md의 REQ-MOBILE-005-* 요구사항 추적 및 AC-001~AC-015 (자동화) / AC-M01~AC-M06 (실기기) 검증 상태를 기록한다.

## Acceptance Criteria (자동화 검증 — MET)

### REQ-MOBILE-005-001: iOS 네이티브 녹음 서비스
- 상태: MET (자동화)
- 증거: client/ios/Runner/AppDelegate.swift — MethodChannel `com.voicetextnote.app/recording` (startBackgroundTask, stopBackgroundTask, flushRecording). AC-001: client/test/services/app_delegate_method_channel_test.dart

### REQ-MOBILE-005-002: 오디오 세션 인터럽션 고도화
- 상태: MET (자동화)
- 증거: client/lib/services/background_recording_service.dart — 인터럽션 begin 시 pause + 상태 업데이트, end 시 shouldResume 확인 후 resume. AC-002/AC-003/AC-004: background_recording_service_test.dart

### REQ-MOBILE-005-003: 오디오 라우트 변경 처리
- 상태: MET (자동화)
- 증거: client/lib/services/background_recording_service.dart — devicesChangedEventStream 구독. AC-005: background_recording_service_test.dart

### REQ-MOBILE-005-004: RecordConfig 및 AudioSession 구성 고도화
- 상태: MET (자동화)
- 증거: client/lib/services/background_recording_service.dart — sampleRate=16000, numChannels=1, bitRate=64000, autoGain/echoCancel/noiseSuppress=true, iosConfig.categoryOptions 5개. AC-006/AC-007/AC-008: background_recording_service_test.dart

### REQ-MOBILE-005-005: 앱 라이프사이클 녹음 보호
- 상태: MET (자동화)
- 증거: client/lib/services/background_recording_service.dart + client/lib/main.dart — paused/inactive/resumed 처리, RecoveryService 연동, 파일 무결성 검사. AC-009/AC-010: background_recording_service_test.dart

### REQ-MOBILE-005-006: 에러 핸들링 및 관측성 개선
- 상태: MET (자동화)
- 증거: client/lib/services/background_recording_service.dart — pause/resume catch 블록 logger 출력, MethodChannel 실패 시 플랫폼 구분 로그. AC-011: background_recording_service_test.dart

## Acceptance Criteria (실기기 검증 — PENDING-HARDWARE-GATE)

아래 AC는 물리적 iOS 기기 + 전화 수신/화면 잠금/Bluetooth route change/강제 종료 시나리오가 필요하며, 자동화 게이트로는 검증 불가.

| AC ID | 요구사항 | 상태 |
|-------|---------|------|
| AC-M01 | 백그라운드 전환 후 녹음 연속성 | PENDING-HARDWARE-GATE |
| AC-M02 | 화면 잠금 후 녹음 연속성 | PENDING-HARDWARE-GATE |
| AC-M03 | 전화 수신 시 녹음 일시정지 | PENDING-HARDWARE-GATE |
| AC-M04 | 전화 종료 후 shouldResume 시 녹음 재개 | PENDING-HARDWARE-GATE |
| AC-M05 | Bluetooth 해제 시 녹음 일시정지 | PENDING-HARDWARE-GATE |
| AC-M06 | 앱 강제 종료 후 재시작 시 복원 다이얼로그 | PENDING-HARDWARE-GATE |

해당 AC는 `verify_release_readiness.py --strict` + `RELEASE_E2E_EVIDENCE_PATH` 통과 시 최종 MET로 전환됨.
