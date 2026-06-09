## Task Decomposition
SPEC: SPEC-APP-005

| Task ID | Description | Requirement | Dependencies | Planned Files | Effort | Status |
|---------|-------------|-------------|--------------|---------------|--------|--------|
| T-001 | RecordingConfig 모델 + Pause/Resume | REQ-001, REQ-003 | - | recording_config.dart, background_recording_service.dart, recording_provider.dart | M | pending |
| T-002 | 오디오 레벨 미터 위젯 | REQ-002 | T-001 | audio_level_meter.dart, recording_provider.dart, recording_screen.dart | M | pending |
| T-003 | 품질 설정 UI + 표시 | REQ-003,004,005 | T-001 | recording_quality_selector.dart, recording_screen.dart | S | pending |
| T-004 | Vocabulary updatedAt 수정 | REQ-008 | - | vocabulary_screen.dart | XS | pending |
| T-005 | PipelineState 확장 | REQ-009,010,011,012,021 | - | pipeline_state.dart, pipeline_progress.dart | L | pending |
| T-006 | 부분 결과 + 단계별 재시도 | REQ-009,010,011,012 | T-005 | partial_result_panel.dart, pipeline_provider.dart, processing_screen.dart | XL | pending |
| T-007 | 청크 업로드 서비스 | REQ-013, REQ-014 | - | upload_service.dart | L | pending |
| T-008 | 캐시 서비스 (Hive) | REQ-016, REQ-018 | - | cache_service.dart, cached_result.dart | L | pending |
| T-009 | 백그라운드 모니터링 + 알림 | REQ-015 | T-005, T-008 | background_pipeline_service.dart, notification_service.dart, main.dart | XL | pending |
| T-010 | 캐시 동기화 알림 | REQ-017 | T-008 | cache_service.dart, cache_provider.dart | S | pending |
| T-011 | 통계 서비스 + 프로바이더 | REQ-019, REQ-021 | T-005, T-008 | processing_stats.dart, stats_service.dart, stats_provider.dart | M | pending |
| T-012 | 통계 화면 + 차트 | REQ-020 | T-011 | stats_screen.dart, stats_chart.dart | M | pending |
