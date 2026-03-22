# SPEC-APP-004 Implementation Plan

## Development Mode: TDD (RED-GREEN-REFACTOR)

---

## Phase 1: SummaryResult 모델 생성 (REQ-APP-040)

### RED
- `client/test/models/summary_result_test.dart` 작성
  - fromJson 전체 필드 파싱 테스트
  - fromJson 부분 필드 테스트 (key_decisions 누락, next_steps 누락)
  - fromJson 빈 객체 테스트 (기본값 확인)
  - ActionItem 중첩 파싱 테스트

### GREEN
- `client/lib/models/summary_result.dart` 생성
  - `SummaryResult` immutable class
  - 필드: summaryText (String), actionItems (List<ActionItem>), keyDecisions (List<String>), nextSteps (List<String>)
  - `factory SummaryResult.fromJson(Map<String, dynamic>)` 구현

### REFACTOR
- 필드 검증 로직 정리

---

## Phase 2: Provider 타입 변환 (REQ-APP-041)

### RED
- `client/test/providers/result_provider_test.dart` 수정
  - summaryResultProvider가 SummaryResult 반환하는 테스트
  - key_decisions/next_steps 파싱 테스트
  - MeetingResult에 keyDecisions/nextSteps 포함 테스트

### GREEN
- `client/lib/providers/result_provider.dart` 수정
  - `summaryResultProvider` 반환 타입: `Map<String, dynamic>` → `SummaryResult`
  - `MeetingResult`에 keyDecisions, nextSteps 필드 추가
  - `resultProvider`에서 key_decisions/next_steps 파싱

### REFACTOR
- _SummaryTab, _ActionItemsTab의 raw Map 접근을 프로퍼티 접근으로 변경

---

## Phase 3: key_decisions/next_steps UI (REQ-APP-042, REQ-APP-043)

### RED
- 위젯 테스트 작성 (result_screen_test.dart 수정)
  - "주요 결정 사항" 섹션 표시 확인
  - "다음 단계" 섹션 표시 확인
  - 빈 배열일 때 섹션 숨김 확인
  - 번호 매기기 표시 확인

### GREEN
- `_SummaryTab` 수정
  - SummaryResult 프로퍼티 기반으로 변환
  - 요약 텍스트 아래에 key_decisions 섹션 추가
  - key_decisions 아래에 next_steps 섹션 추가
  - 각 섹션: 제목 + 번호 매기기 리스트
  - 빈 배열이면 섹션 숨김

### REFACTOR
- 반복되는 섹션 빌드 로직 추출

---

## Phase 4: API 서비스 테스트 보완 (REQ-APP-044)

### RED + GREEN
- `client/test/services/summary_api_test.dart` 신규
- `client/test/services/minutes_api_test.dart` 신규
- `client/test/services/diarization_api_test.dart` 신규
- 각각 create, getStatus, getResult, delete 메서드 테스트

---

## Phase 5: 통합 검증

- `flutter test` 전체 실행
- `dart analyze` 경고 0개 확인
- 기존 테스트 회귀 없음 확인

---

## Risk Analysis

| 리스크 | 확률 | 대응 |
|--------|------|------|
| summaryResultProvider 타입 변경 시 기존 코드 컴파일 에러 | 높음 | _SummaryTab, _ActionItemsTab 동시 수정 |
| 기존 result_provider_test.dart 실패 | 높음 | Phase 2에서 함께 수정 |
| API 서비스 Dio 모킹 복잡도 | 중간 | 기존 health_api_test.dart 패턴 참조 |

## Dependencies

- SPEC-APP-003의 ActionItem 모델 재사용
- 백엔드 변경 없음
- 기존 위젯 재사용
