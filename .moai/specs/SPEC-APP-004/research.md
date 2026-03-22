# SPEC-APP-004 Research: Summary 결과 화면 완성도 개선

## 1. Architecture Analysis

### Backend API Response (변경 없음)

**Schema** (`backend/schemas/summary.py:51-73`):
```
SummaryResponse {
  task_id: str
  status: TaskStatus
  minutes_task_id: str
  summary_text: str           # 요약 텍스트
  action_items: list[ActionItem]  # SPEC-APP-003에서 처리 완료
  key_decisions: list[str]    # ← Flutter에서 미사용
  next_steps: list[str]       # ← Flutter에서 미사용
  tokens_used: dict | None
  generation_time_seconds: float | None
}
```

**API Endpoint** (`backend/app/api/v1/summary.py:195-196`):
- `GET /api/v1/summaries/{task_id}` returns `SummaryResponse`
- `key_decisions` and `next_steps` are populated from Redis data

### Flutter Client (수정 대상)

**문제 1: _SummaryTab이 key_decisions/next_steps 미표시**
- `result_screen.dart:151-182`: `_SummaryTab`은 `data['summary_text']`만 렌더링
- `key_decisions`와 `next_steps`는 API에서 반환되지만 완전히 무시됨

**문제 2: summaryResultProvider가 raw Map 반환**
- `result_provider.dart:52-56`: `FutureProvider.family<Map<String, dynamic>, String>`
- 호출부에서 `data['key']` 문자열 키로 접근 → 타입 안전성 없음
- _SummaryTab, _ActionItemsTab 모두 이 raw Map에 의존

**문제 3: MeetingResult에 key_decisions/next_steps 필드 누락**
- `result_provider.dart:7-22`: `MeetingResult` 클래스에 3개 필드만 존재
- `resultProvider`(통합 프로바이더)에서도 해당 필드 미파싱

**문제 4: API 서비스 테스트 누락**
- `summary_api.dart`, `minutes_api.dart`, `diarization_api.dart` 테스트 없음
- `health_api_test.dart`, `transcription_api_test.dart`만 존재

## 2. Data Flow Trace

```
Backend API Response (JSON)
  → Dio HTTP Client (summary_api.dart:30)
  → Map<String, dynamic> (raw)
  → summaryResultProvider (result_provider.dart:52)
  → _SummaryTab: data['summary_text'] 만 사용
                  data['key_decisions'] 무시 ← BUG
                  data['next_steps'] 무시   ← BUG
  → _ActionItemsTab: data['action_items'] 사용 (SPEC-APP-003 완료)
```

## 3. Existing Patterns

**UI 패턴** (`result_screen.dart`):
- Card + Column + Text 레이아웃 (_SummaryTab)
- ListView.builder 패턴 (_ActionItemCardList)
- EmptyStateWidget, ErrorRetryWidget 재사용

**모델 패턴** (`action_item.dart`):
- immutable class, fromJson/toJson
- const 생성자, nullable 필드

## 4. Recommendations

1. `SummaryResult` Dart 모델 생성 (타입 안전 파싱)
2. `summaryResultProvider` 반환 타입을 `SummaryResult`로 변경
3. `_SummaryTab`에 key_decisions/next_steps 섹션 추가
4. `MeetingResult`에 key_decisions/next_steps 필드 추가
5. 누락 API 서비스 테스트 보완
