---
name: Voice to TextNote Flutter Client
description: Flutter MVP 클라이언트 구현 완료 상태 및 아키텍처 정보
type: project
---

# Voice to TextNote Flutter Client MVP

SPEC-APP-001 TDD 방식으로 구현 완료

## 구현된 구조

```
client/lib/
  config/app_config.dart        - API 설정 상수
  models/
    meeting.dart                - Meeting 모델 (fromJson/toJson 수동 구현)
    pipeline_state.dart         - PipelineState 모델
  services/
    api_client.dart             - Dio 싱글톤 (Riverpod Provider)
    transcription_api.dart      - STT API
    diarization_api.dart        - 화자 분리 API
    minutes_api.dart            - 회의록 API
    summary_api.dart            - 요약 API
    health_api.dart             - 헬스체크 API
  providers/
    recording_provider.dart     - 녹음 상태 관리
    pipeline_provider.dart      - 파이프라인 처리 상태
    meeting_list_provider.dart  - 미팅 목록 관리
  screens/
    home_screen.dart            - 홈 화면
    recording_screen.dart       - 녹음 화면
    processing_screen.dart      - 처리 중 화면
    result_screen.dart          - 결과 화면 (3탭)
  widgets/
    meeting_card.dart           - 미팅 목록 카드
    pipeline_progress.dart      - 파이프라인 진행 표시
    speaker_segment.dart        - 화자 발화 세그먼트
  router/app_router.dart        - go_router 설정
  main.dart                     - 앱 진입점 (ProviderScope)
```

## 테스트 현황
- 전체 37개 테스트 통과
- flutter analyze: 이슈 없음

## 기술 스택
- Flutter Riverpod (NotifierProvider 패턴)
- go_router (파일 경로 라우팅)
- Dio (HTTP 클라이언트)
- mocktail (테스트 모킹)
- NO freezed, NO json_serializable (수동 직렬화)

**Why:** SPEC-APP-001 지침: freezed/json_serializable 버전 충돌로 제거
**How to apply:** 새 모델 추가 시 항상 수동 fromJson/toJson 구현
