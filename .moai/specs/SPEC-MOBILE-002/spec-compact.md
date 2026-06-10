---
id: SPEC-MOBILE-002
version: "1.0.0"
status: implementation-complete
created: "2026-06-10"
updated: "2026-06-11"
author: kisoo
priority: medium
---

# SPEC-MOBILE-002: Compact Reference

## Requirements Summary

### REQ-MOBILE-007: 온디바이스 Whisper 모델 관리

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-007-01 | whisper-base 모델 파일(~150MB) 다운로드 및 저장 | P1 |
| REQ-MOBILE-007-02 | SHA-256 체크섬 무결성 검증 | P1 |
| REQ-MOBILE-007-03 | 모델 버전 관리 및 업데이트 트리거 | P2 |
| REQ-MOBILE-007-04 | 저장 공간 부족 시 다운로드 차단 및 안내 | P1 |
| REQ-MOBILE-007-05 | Resumable download (이어서 다운로드) | P2 |
| REQ-MOBILE-007-06 | 앱 내부 저장소 보관 (앱 삭제 시 자동 제거) | P1 |

### REQ-MOBILE-008: 오프라인 STT 처리 엔진

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-008-01 | M4A → 16kHz mono WAV 오디오 전처리 | P1 |
| REQ-MOBILE-008-02 | whisper.cpp Flutter 플랫폼 채널 온디바이스 추론 | P1 |
| REQ-MOBILE-008-03 | STT 처리 진행률 실시간 UI 표시 (0%~100%) | P2 |
| REQ-MOBILE-008-04 | 메모리 사용량 모니터링 및 부족 시 안전 중단 | P1 |
| REQ-MOBILE-008-05 | 5분 초과 녹음 30초 청크 분할 순차 처리 | P1 |
| REQ-MOBILE-008-06 | 임시 WAV 파일 즉시 삭제 | P2 |
| REQ-MOBILE-008-07 | 오프라인 결과에 `offline: true` 메타데이터 부여 | P1 |

### REQ-MOBILE-009: 하이브리드 온/오프라인 파이프라인

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-009-01 | ConnectivityService 네트워크 상태 변경 구독 | P1 |
| REQ-MOBILE-009-02 | 오프라인 시 로컬 STT 파이프라인 자동 실행 | P1 |
| REQ-MOBILE-009-03 | 온라인 시 기존 백엔드 파이프라인 우선 실행 | P1 |
| REQ-MOBILE-009-04 | 네트워크 복구 시 `offline: true` 결과 자동 재전송 | P1 |
| REQ-MOBILE-009-05 | 재처리 완료 시 온라인 결과 교체 + "개선됨" 배지 | P2 |
| REQ-MOBILE-009-06 | 재처리 실패 시 기존 결과 유지 + 수동 재시도 | P1 |
| REQ-MOBILE-009-07 | PipelineProvider 하이브리드 통합 (SSE+폴링 일관성) | P1 |

### REQ-MOBILE-010: 모델 다운로드 UX

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-010-01 | 모델 미다운로드 시 다운로드 안내 다이얼로그 | P1 |
| REQ-MOBILE-010-02 | Wi-Fi 자동 다운로드, 셀룰러 사용자 확인 | P1 |
| REQ-MOBILE-010-03 | 진행률 퍼센트 + 예상 남은 시간 표시 | P2 |
| REQ-MOBILE-010-04 | 네트워크 끊김 시 일시 정지, 복구 시 자동 재개 | P1 |
| REQ-MOBILE-010-05 | 최대 3회 자동 재시도, 실패 시 수동 재시도 | P2 |
| REQ-MOBILE-010-06 | 백그라운드 다운로드 지원 | P2 |

### REQ-MOBILE-011: 플랫폼별 STT 통합

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| REQ-MOBILE-011-01 | iOS whisper.cpp + Core ML Neural Engine 가속 | P1 |
| REQ-MOBILE-011-02 | macOS mlx-whisper 직접 호출 (MPS 가속) | P1 |
| REQ-MOBILE-011-03 | Android whisper.cpp + TFLite (ARM NEON) | P1 |
| REQ-MOBILE-011-04 | 플랫폼 자동 감지 및 적절한 엔진 로드 | P1 |
| REQ-MOBILE-011-05 | Flutter MethodChannel Dart ↔ 네이티브 통신 | P1 |
| REQ-MOBILE-011-06 | 플랫폼별 성능 벤치마크 로깅 | P2 |

---

## Acceptance Criteria Summary

### REQ-MOBILE-007 인수 기준
- AC-007-01: 모델 다운로드 → SHA-256 검증 → 활성화
- AC-007-02: 체크섬 불일치 시 파일 삭제 + 재다운로드
- AC-007-03: 저장 공간 부족(300MB 미만) 시 다운로드 차단
- AC-007-04: 다운로드 중단 시 이어서 다운로드 (resumable)
- AC-007-05: 앱 삭제 시 모델 자동 제거

### REQ-MOBILE-008 인수 기준
- AC-008-01: 오프라인 + 모델 존재 → M4A→WAV→STT→텍스트 결과
- AC-008-02: 10분 오디오 → 30초 청크 분할 → 순차 처리 → 병합
- AC-008-03: 메모리 부족 시 안전 중단 + 사용자 안내
- AC-008-04: STT 완료 후 임시 WAV 삭제, 원본 M4A 유지
- AC-008-05: 결과에 `offline: true` 메타데이터 + UI 배지
- AC-008-06: 청크 진행률 실시간 업데이트 (0%~100%)

### REQ-MOBILE-009 인수 기준
- AC-009-01: 오프라인 → 로컬 STT 자동 실행
- AC-009-02: 온라인 → 기존 백엔드 파이프라인 실행
- AC-009-03: 오프라인→온라인 전환 → 자동 백엔드 재처리
- AC-009-04: 재처리 실패 → 기존 결과 유지 + 수동 재시도
- AC-009-05: 재처리 완료 → "개선된 결과" 배지
- AC-009-06: 네트워크 전환 중 상태 일관성 유지

### REQ-MOBILE-010 인수 기준
- AC-010-01: Wi-Fi → 즉시 다운로드
- AC-010-02: 셀룰러 → 확인 다이얼로그
- AC-010-03: 진행률 퍼센트 + 예상 남은 시간
- AC-010-04: 네트워크 끊김 → 일시 정지 → 복구 시 재개
- AC-010-05: 3회 실패 → 수동 재시도 버튼

### REQ-MOBILE-011 인수 기준
- AC-011-01: iOS Core ML ANE 가속 (CPU 대비 2배+)
- AC-011-02: macOS mlx-whisper MPS 가속
- AC-011-03: Android TFLite + NNAPI
- AC-011-04: 플랫폼 자동 감지 + 엔진 선택
- AC-011-05: MethodChannel 통신 정상 동작

---

## Files to Modify

### New Files (14)

| File | Description |
|------|-------------|
| `client/lib/services/offline_stt_service.dart` | 오프라인 STT 오케스트레이터 |
| `client/lib/services/model_download_service.dart` | 모델 다운로드/검증/버전 관리 |
| `client/lib/services/audio_preprocessor.dart` | M4A → 16kHz WAV 변환 |
| `client/lib/services/hybrid_pipeline_service.dart` | 온/오프라인 파이프라인 분기 |
| `client/lib/services/platform_stt_service.dart` | Platform Channel 바인딩 |
| `client/lib/providers/offline_stt_provider.dart` | 오프라인 STT 상태 (Riverpod) |
| `client/lib/providers/model_download_provider.dart` | 다운로드 진행률 상태 |
| `client/lib/models/model_info.dart` | 모델 버전/상태 정보 |
| `client/lib/widgets/model_download_dialog.dart` | 다운로드 진행 UI |
| `client/lib/widgets/offline_result_badge.dart` | "오프라인 처리됨" 배지 |
| `client/lib/widgets/improved_result_badge.dart` | "개선된 결과" 배지 |
| `client/ios/Classes/WhisperSttPlugin.swift` | iOS whisper.cpp + Core ML |
| `client/macos/Classes/MlxWhisperPlugin.swift` | macOS mlx-whisper |
| `client/android/app/src/main/kotlin/com/voicetextnote/app/WhisperSttPlugin.kt` | Android whisper.cpp + TFLite |

### Modified Files (5)

| File | Change Scope |
|------|-------------|
| `client/lib/providers/pipeline_provider.dart` | MODERATE — 하이브리드 파이프라인 분기 |
| `client/lib/models/transcription_result.dart` | MINOR — `offline` 필드 추가 |
| `client/lib/screens/recording_screen.dart` | MINOR — 오프라인 STT 트리거 |
| `client/pubspec.yaml` | MINOR — 의존성 4개 추가 |
| `client/lib/services/connectivity_service.dart` | MINOR — 상태 이벤트 확장 |

---

## Exclusions

| 기능 | 제외 사유 | 향후 SPEC |
|------|----------|----------|
| 실시간 스트리밍 STT | whisper.cpp 배치 처리 최적화, 실시간은 추가 아키텍처 필요 | SPEC-MOBILE-003 |
| 다국어 STT | 한국어 우선 검증 후 확장 | SPEC-I18N-001 |
| 온디바이스 화자 분리 | pyannote 모델 크기 1GB+, GPU 필요 | N/A |
| 오프라인 AI 요약 | 로컬 LLM 비실용적 | N/A |
| 모델 자동 압축/양자화 | 공식 모델 우선, 성능 검증 후 | SPEC-MOBILE-004 |

---

*SPEC ID: SPEC-MOBILE-002*
*문서: spec-compact.md*
