# SPEC-APP-003 Research: Action Items Flutter UI

## 1. Architecture Analysis

### Backend (No changes needed)

**Schema** (`backend/schemas/summary.py:11-24`):
```
ActionItem {
  assignee: str | None    # 담당자
  task: str               # 작업 내용 (필수)
  deadline: str | None    # 마감일 (자유 형식)
  priority: str           # low/medium/high (기본: medium)
}
```

**API Response** (`backend/app/api/v1/summary.py:132-199`):
- `GET /api/v1/summaries/{task_id}` returns `SummaryResponse`
- `action_items: list[ActionItem]` — 구조화된 객체 배열 반환
- `key_decisions: list[str]`, `next_steps: list[str]` 포함

**AI Prompt** (`backend/pipeline/summary_generator.py:59-75`):
- OpenAI API에 JSON 형식으로 액션 아이템 추출 지시
- assignee, task, deadline, priority 4개 필드 명시

### Flutter Client (수정 대상)

**현재 문제점**:

1. **result_provider.dart:15** — `MeetingResult.actionItems`가 `List<String>`
   - 백엔드는 `List<{assignee, task, deadline, priority}>` 반환
   - `cast<String>()` 호출 시 런타임 타입 에러 가능

2. **result_screen.dart:234** — `(data['action_items'] as List<dynamic>).cast<String>()`
   - 실제 데이터가 Map이면 `TypeError` 발생

3. **result_screen.dart:265-308** — `_ActionItemsList`
   - 단순 `List<String>` + CheckboxListTile
   - 담당자, 마감일, 우선순위 정보 미표시

4. **summary_api.dart:30** — `getResult()`가 `Map<String, dynamic>` 원시 반환
   - 타입 안전성 없음, 호출 측에서 수동 파싱 필요

## 2. Data Flow Trace

```
Backend API Response (JSON)
  → Dio HTTP Client (summary_api.dart:30)
  → Map<String, dynamic> (raw)
  → summaryResultProvider (result_provider.dart:52)
  → _ActionItemsTab (result_screen.dart:209)
  → .cast<String>() ← BUG: Map을 String으로 캐스팅
  → _ActionItemsList (result_screen.dart:265)
  → CheckboxListTile (단순 텍스트)
```

## 3. Existing Patterns (Reference Implementations)

**Riverpod Provider 패턴** (`result_provider.dart:27-47`):
- `minutesResultProvider` — FutureProvider.family 패턴 사용
- raw Map에서 필요한 데이터 추출

**UI 위젯 패턴** (`result_screen.dart`):
- `_SummaryTab` — Card + Column + Text 레이아웃
- `_TranscriptTab` — ListView + SpeakerSegment
- Shimmer 로딩, EmptyState, ErrorRetry 위젯 재사용

**API 서비스 패턴** (`summary_api.dart`):
- Dio 기반, `Map<String, dynamic>` 반환
- Provider를 통한 DI

## 4. Risks & Constraints

- **런타임 에러**: 현재 코드는 AI가 action_items를 반환하면 `cast<String>()` 에서 크래시 가능
- **하위 호환**: `resultProvider` (result_provider.dart:60-80)도 동일 버그 존재
- **체크 상태 비영속**: 체크박스 상태가 메모리에만 존재 (앱 재시작 시 초기화)
- **key_decisions, next_steps**: 현재 UI에 미표시 — 이 SPEC 범위 외

## 5. Recommendations

1. `ActionItem` Dart 모델 클래스 생성 (freezed 권장)
2. `summaryResultProvider`에서 `ActionItem` 리스트로 파싱
3. `_ActionItemsTab` UI를 Card 기반 리치 위젯으로 교체
4. 우선순위별 색상 배지, 담당자/마감일 표시
5. 기존 `MeetingResult.actionItems` 타입을 `List<ActionItem>`으로 변경
