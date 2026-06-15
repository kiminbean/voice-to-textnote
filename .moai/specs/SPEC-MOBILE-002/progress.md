# SPEC-MOBILE-002 Progress

## 상태: COMPLETED

## 완료 증거

### 코드
- client/lib/services/local_stt_service.dart — on-device whisper 추론 코어 (16kHz mono WAV, 한국어 고정)
- client/lib/services/local_stt_provider.dart — SttModelManager + WhisperGgmlLocalSttRuntime 주입
- client/lib/services/local_stt_runtime_whisper.dart — whisper_ggml_plus FFI adapter (Whisper.transcribe)
- client/lib/services/model_manager.dart — 모델 다운로드/SHA-256 검증/버전 관리
- client/lib/services/reprocess_queue.dart — 네트워크 복구 시 서버 STT 재처리 큐
- client/pubspec.yaml — whisper_ggml_plus 1.5.2 고정

### 테스트
- client/tool/local_stt_smoke.dart — fake runtime 기반 서비스 계약 smoke runner (`local_stt_smoke: PASS`)
- client/scripts/verify_mobile.sh — pub get / analyze / test / local STT smoke / native build 게이트
- client/scripts/verify_release_readiness.py — whisper_ggml_plus FFI adapter/provider/Pod lock 게이트

### 주요 커밋
- 5fa1802: feat(mobile-002): 오프라인 STT 하이브리드 파이프라인 — 모델 관리 + 로컬 전사 + 재처리 큐
- 8660178: Prove mobile STT readiness up to native-environment limits

## phase log
- Plan: completed (plan.md 존재)
- Implementation: completed
- Verification: flutter test 328 passed / verify_mobile.sh --native APK+iOS build 통과 / release readiness 0 errors

## 비고
- 네이티브 모바일 런타임 검증 완료 (session-memo 2026-06-14): Android APK debug build + iOS no-codesign build 통과, whisper_ggml_plus 1.5.2 FFI 링크 확인.
- Flutter tester 환경 제약으로 local_stt_service_test.dart는 socket 생성 실패. 동일 서비스 계약은 smoke runner로 검증.
