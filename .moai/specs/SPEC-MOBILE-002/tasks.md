## Task Decomposition
SPEC: SPEC-MOBILE-002

| Task ID | Description | Requirement | Dependencies | Planned Files | Status |
|---------|-------------|-------------|--------------|---------------|--------|
| T-001 | ModelInfo 데이터 모델 | REQ-MOBILE-007 | - | client/lib/models/model_info.dart | done |
| T-002 | OfflineTask 데이터 모델 | REQ-MOBILE-009 | - | client/lib/models/offline_task.dart | done |
| T-003 | TranscriptionResult offline 필드 확장 | REQ-MOBILE-008-07 | - | client/lib/models/transcription_result.dart (mod) | done |
| T-004 | PlatformSttService 인터페이스 | REQ-MOBILE-011-05 | - | client/lib/services/platform_stt_service.dart | done |
| T-005 | PlatformSttService Mock 인프라 | REQ-MOBILE-011 | T-004 | client/test/mocks/mock_platform_stt_service.dart | done |
| T-006 | ConnectivityService 상태 이벤트 확장 | REQ-MOBILE-009-01 | - | client/lib/services/connectivity_service.dart (mod) | done |
| T-007 | ModelDownloadService 기본 다운로드 | REQ-MOBILE-007-01, REQ-MOBILE-010-01 | T-001 | client/lib/services/model_download_service.dart | done |
| T-008 | ModelDownloadService SHA-256 검증 | REQ-MOBILE-007-02 | T-007 | client/lib/services/model_download_service.dart (ext) | done |
| T-009 | ModelDownloadService 저장공간 + Resumable | REQ-MOBILE-007-03, REQ-MOBILE-007-04 | T-007 | client/lib/services/model_download_service.dart (ext) | done |
| T-010 | ModelDownloadProvider (Riverpod) | REQ-MOBILE-010 | T-007~T-009 | client/lib/providers/model_download_provider.dart | done |
| T-011 | ModelDownloadDialog 위젯 | REQ-MOBILE-010-01, REQ-MOBILE-010-03 | T-010 | client/lib/widgets/model_download_dialog.dart | done |
| T-012 | AudioPreprocessor M4A→WAV 변환 | REQ-MOBILE-008-01 | T-004 | client/lib/services/audio_preprocessor.dart | done |
| T-013 | OfflineSttService 기본 추론 흐름 | REQ-MOBILE-008-01, REQ-MOBILE-008-07 | T-004, T-012 | client/lib/services/offline_stt_service.dart | done |
| T-014 | OfflineSttService 청크 분할 처리 | REQ-MOBILE-008-05 | T-013 | client/lib/services/offline_stt_service.dart (ext) | done |
| T-015 | OfflineSttService 메모리 모니터링 + 진행률 | REQ-MOBILE-008-03, REQ-MOBILE-008-06 | T-014 | client/lib/services/offline_stt_service.dart (ext) | done |
| T-016 | OfflineSttProvider (Riverpod) | REQ-MOBILE-008 | T-013~T-015 | client/lib/providers/offline_stt_provider.dart | done |
| T-017 | HybridPipelineService 온/오프라인 분기 | REQ-MOBILE-009-01~03 | T-006, T-016 | client/lib/services/hybrid_pipeline_service.dart | done |
| T-018 | HybridPipelineService 네트워크 복구 자동 재처리 | REQ-MOBILE-009-04 | T-017 | client/lib/services/hybrid_pipeline_service.dart (ext) | done |
| T-019 | HybridPipelineService 재처리 실패 + 수동 재시도 | REQ-MOBILE-009-05, REQ-MOBILE-009-06 | T-018 | client/lib/services/hybrid_pipeline_service.dart (ext) | done |
| T-020 | PipelineProvider 하이브리드 통합 | REQ-MOBILE-009-07 | T-017 | client/lib/providers/pipeline_provider.dart (mod) | done |
| T-021 | OfflineResultBadge + ImprovedResultBadge 위젯 | REQ-MOBILE-008-05, REQ-MOBILE-009-05 | T-003 | client/lib/widgets/offline_result_badge.dart, client/lib/widgets/improved_result_badge.dart | done |
| T-022 | WhisperSttPlugin.swift 스켈레톤 (iOS) | REQ-MOBILE-011-01 | T-004 | client/ios/Classes/WhisperSttPlugin.swift | done |
| T-023 | MlxWhisperPlugin.swift 스켈레톤 (macOS) | REQ-MOBILE-011-02 | T-004 | client/macos/Classes/MlxWhisperPlugin.swift | done |
| T-024 | WhisperSttPlugin.kt 스켈레톤 (Android) | REQ-MOBILE-011-03 | T-004 | client/android/app/src/main/kotlin/com/voicetextnote/app/WhisperSttPlugin.kt | done |
