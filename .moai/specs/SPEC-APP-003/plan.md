# SPEC-APP-003 Implementation Plan

## Development Mode: TDD (RED-GREEN-REFACTOR)

---

## Phase 1: ActionItem 모델 생성 (REQ-APP-030)

### RED
- `client/test/models/action_item_test.dart` 작성
  - fromJson 정상 파싱 테스트 (전체 필드)
  - fromJson 부분 필드 테스트 (assignee=null, deadline=null)
  - fromJson 빈 객체 테스트 (기본값 확인)
  - priority 기본값 "medium" 테스트
  - 불변성 테스트

### GREEN
- `client/lib/models/action_item.dart` 생성
  - `ActionItem` immutable class
  - 필드: assignee (String?), task (String), deadline (String?), priority (String)
  - `factory ActionItem.fromJson(Map<String, dynamic>)` 구현
  - `toJson()` 메서드 (선택)

### REFACTOR
- 필드 검증 로직 정리
- 코드 문서화

---

## Phase 2: Provider 파싱 수정 (REQ-APP-031)

### RED
- `client/test/providers/result_provider_test.dart` 수정
  - action_items가 Map 배열일 때 `List<ActionItem>` 파싱 테스트
  - action_items가 빈 배열일 때 빈 리스트 테스트
  - action_items 필드 누락 시 빈 리스트 테스트
  - 잘못된 형식 데이터 graceful 처리 테스트

### GREEN
- `client/lib/providers/result_provider.dart` 수정
  - `MeetingResult.actionItems` 타입: `List<String>` → `List<ActionItem>`
  - `summaryResultProvider` → ActionItem 전용 provider 추가 또는 기존 provider에서 파싱
  - `resultProvider`의 `.cast<String>()` 제거, `ActionItem.fromJson()` 사용

### REFACTOR
- 중복 파싱 로직 추출
- Provider 간 데이터 흐름 정리

---

## Phase 3: 액션 아이템 카드 UI (REQ-APP-032, REQ-APP-033)

### RED
- 위젯 테스트 작성
  - ActionItem 카드에 담당자, 작업, 마감일, 우선순위 표시 확인
  - 우선순위별 배지 색상 확인 (high=빨강, medium=주황, low=초록)
  - 체크박스 토글 동작 확인
  - 필터 칩 탭 시 필터링 동작 확인
  - 빈 상태 / 에러 상태 위젯 표시 확인

### GREEN
- `_ActionItemsTab` 리팩토링
  - `List<ActionItem>` 기반으로 변경
  - 우선순위 필터 칩 행 추가 (전체/High/Medium/Low)
- `_ActionItemsList` → `_ActionItemCard` 기반으로 교체
  - Card 위젯: 체크박스 + 작업 내용 (title)
  - Subtitle: 담당자 + 마감일
  - Leading/Trailing: 우선순위 배지
- 기존 Shimmer/Empty/Error 위젯 재사용

### REFACTOR
- 위젯 분리 정리
- 테마 색상 상수화

---

## Phase 4: 통합 검증

- `flutter test` 전체 실행
- `dart analyze` 경고 0개 확인
- 기존 테스트 회귀 없음 확인

---

## Risk Analysis

| 리스크 | 확률 | 대응 |
|--------|------|------|
| AI가 action_items를 빈 배열로 반환 | 중간 | 빈 상태 UI로 graceful 처리 |
| 기존 테스트가 List<String> 기대 | 높음 | Phase 2에서 테스트도 함께 수정 |
| freezed 의존성 추가 복잡도 | 낮음 | 수동 immutable class로 대체 가능 |

## Dependencies

- 백엔드 변경 없음
- 기존 위젯 (EmptyStateWidget, ErrorRetryWidget, ShimmerText) 재사용
- Riverpod, Dio 기존 의존성 활용
