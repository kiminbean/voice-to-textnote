---
spec_id: SPEC-APP-001
type: plan
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-APP-001 구현 계획: Flutter 클라이언트 MVP

---

## 1. 구현 개요

### 목표

백엔드 4개 파이프라인(STT/DIA/MIN/SUM) API를 연동하는 Flutter 클라이언트 MVP 구현.

### 구현 순서 (6 TASK)

| TASK | 파일 | 핵심 역할 |
|------|------|----------|
| TASK-001 | Flutter 프로젝트 생성 | `flutter create` + 의존성 추가 |
| TASK-002 | 데이터 모델 + AppConfig | Meeting, PipelineState, AppConfig |
| TASK-003 | API 서비스 레이어 | TranscriptionApi, DiarizationApi, MinutesApi, SummaryApi, HealthApi |
| TASK-004 | 상태 관리 (Riverpod) | RecordingNotifier, PipelineNotifier, MeetingListNotifier |
| TASK-005 | UI 화면 | HomeScreen, RecordingScreen, ProcessingScreen, ResultScreen |
| TASK-006 | 라우팅 + 앱 통합 | go_router 설정, main.dart 통합 |

### 디렉토리 구조

```
client/
├── lib/
│   ├── main.dart
│   ├── config/
│   │   └── app_config.dart
│   ├── models/
│   │   ├── meeting.dart
│   │   └── pipeline_state.dart
│   ├── services/
│   │   ├── api_client.dart
│   │   ├── transcription_api.dart
│   │   ├── diarization_api.dart
│   │   ├── minutes_api.dart
│   │   ├── summary_api.dart
│   │   └── health_api.dart
│   ├── providers/
│   │   ├── recording_provider.dart
│   │   ├── pipeline_provider.dart
│   │   └── meeting_list_provider.dart
│   ├── screens/
│   │   ├── home_screen.dart
│   │   ├── recording_screen.dart
│   │   ├── processing_screen.dart
│   │   └── result_screen.dart
│   ├── widgets/
│   │   ├── meeting_card.dart
│   │   ├── pipeline_progress.dart
│   │   └── speaker_segment.dart
│   └── router/
│       └── app_router.dart
├── test/
│   ├── services/
│   │   ├── api_client_test.dart
│   │   ├── transcription_api_test.dart
│   │   └── health_api_test.dart
│   ├── providers/
│   │   ├── recording_provider_test.dart
│   │   └── pipeline_provider_test.dart
│   └── screens/
│       ├── home_screen_test.dart
│       └── recording_screen_test.dart
├── pubspec.yaml
└── README.md
```

---

## 2. TDD 테스트 전략

### 단위 테스트

| 테스트 파일 | 핵심 케이스 |
|------------|------------|
| api_client_test.dart | Dio 초기화, 타임아웃, 에러 인터셉터 |
| transcription_api_test.dart | 파일 업로드 mock, 상태 조회, 결과 조회 |
| health_api_test.dart | 서버 연결 성공/실패 |
| recording_provider_test.dart | 상태 전이 (idle→recording→stopped) |
| pipeline_provider_test.dart | 단계별 진행, 자동 다음 단계, 실패 처리 |

### 위젯 테스트

| 테스트 파일 | 핵심 케이스 |
|------------|------------|
| home_screen_test.dart | 빈 목록 표시, 회의 카드 렌더링 |
| recording_screen_test.dart | 녹음 버튼 표시, 타이머 표시 |

---

## 3. 리스크 매트릭스

| 리스크 | 확률 | 완화 전략 |
|--------|------|----------|
| record 패키지 Web 지원 제한 | 중간 | macOS 우선, Web은 조건부 지원 |
| 파이프라인 폴링 과부하 | 낮음 | 2초 간격 폴링 + debounce |
| Dio mock 복잡성 | 낮음 | dio_test 또는 http_mock_adapter 활용 |

---

*Plan ID: SPEC-APP-001*
*생성일: 2026-03-15*
*상태: completed*
