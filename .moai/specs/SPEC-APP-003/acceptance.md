# SPEC-APP-003 Acceptance Criteria

---

## AC-1: ActionItem 모델 파싱 (REQ-APP-030)

**Given** 백엔드가 다음 JSON을 반환할 때:
```json
{
  "action_items": [
    {"assignee": "김철수", "task": "디자인 검토", "deadline": "2026-03-25", "priority": "high"},
    {"assignee": null, "task": "코드 리뷰", "deadline": null, "priority": "medium"}
  ]
}
```
**When** Flutter 클라이언트가 응답을 파싱하면
**Then** 2개의 `ActionItem` 객체가 생성되고, 각 필드가 정확히 매핑된다.

---

## AC-2: Graceful 파싱 실패 처리 (REQ-APP-031)

**Given** 백엔드가 잘못된 형식의 action_items를 반환할 때 (예: 문자열 배열, null)
**When** Flutter 클라이언트가 응답을 파싱하면
**Then** 런타임 에러 없이 빈 `List<ActionItem>`을 반환한다.

---

## AC-3: 액션 아이템 카드 표시 (REQ-APP-032)

**Given** 요약 결과에 액션 아이템이 존재할 때
**When** 사용자가 '액션 아이템' 탭을 선택하면
**Then** 각 아이템이 카드 형태로 표시되며:
- 작업 내용이 메인 텍스트로 표시됨
- 담당자가 표시됨 (null이면 "미지정")
- 마감일이 표시됨 (null이면 미표시)
- 우선순위 배지가 색상으로 구분됨 (high=빨강, medium=주황, low=초록)
- 체크박스가 포함됨

---

## AC-4: 우선순위 필터링 (REQ-APP-033)

**Given** 여러 우선순위의 액션 아이템이 표시된 상태에서
**When** 사용자가 "High" 필터 칩을 탭하면
**Then** priority가 "high"인 아이템만 표시된다.

**Given** 필터가 적용된 상태에서
**When** 사용자가 "전체" 필터 칩을 탭하면
**Then** 모든 아이템이 다시 표시된다.

---

## AC-5: 빈 상태 표시 (REQ-APP-034)

**Given** 요약 결과에 액션 아이템이 비어있을 때
**When** 사용자가 '액션 아이템' 탭을 선택하면
**Then** "액션 아이템이 없습니다" EmptyStateWidget이 표시된다.

---

## AC-6: 기존 기능 회귀 없음

**Given** SPEC-APP-003 변경사항이 적용된 후
**When** `flutter test` 전체 테스트를 실행하면
**Then** 기존 테스트가 모두 통과하고, 새 테스트를 포함하여 85% 이상 커버리지를 달성한다.

---

## Quality Gates

- [ ] `dart analyze` 경고 0개
- [ ] `flutter test` 전체 통과
- [ ] 테스트 커버리지 85% 이상
- [ ] 런타임 타입 에러 해결 확인
