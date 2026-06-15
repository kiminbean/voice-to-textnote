# SPEC-MOBILE-002 Acceptance Criteria

## 검증 방법
본 문서는 spec.md의 REQ-MOBILE-002-* 요구사항이 코드와 테스트로 충족되었는지 추적한다.

## Acceptance Criteria

### REQ-MOBILE-002-001: 모델 관리
- 상태: MET
- 증거: client/lib/services/model_manager.dart — whisper-base 모델 다운로드 URL, SHA-256 체크섬 검증, 버전 관리, 앱 문서 디렉토리 경로 관리

### REQ-MOBILE-002-002: 오프라인 STT 엔진
- 상태: MET
- 증거: client/lib/services/local_stt_runtime_whisper.dart — whisper_ggml_plus FFI (whisper.cpp) 추론, 16kHz mono WAV 전처리, 한국어 고정, 세그먼트별 타임스탬프

### REQ-MOBILE-002-003: 하이브리드 파이프라인
- 상태: MET
- 증거: client/lib/services/local_stt_service.dart + client/lib/services/reprocess_queue.dart — 오프라인 시 로컬 STT 우선, low-confidence 임시 표시, 네트워크 복구 시 서버 재처리, ConnectivityProvider 기반 자동 분기

### REQ-MOBILE-002-004: 모델 다운로드 UX
- 상태: MET
- 증거: client/lib/services/model_manager.dart — Wi-Fi 확인, 진행률 UI, 재시도 로직

### REQ-MOBILE-002-005: 백엔드 재처리 지원
- 상태: MET
- 증거: client/lib/services/local_stt_service.dart — local_result 메타데이터 전달, transcription_source 필드 (local/server/hybrid), 기존 파이프라인 호환성 유지
