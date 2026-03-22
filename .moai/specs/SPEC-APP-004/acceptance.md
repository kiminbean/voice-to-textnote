# SPEC-APP-004 Acceptance Criteria

---

## AC-1: SummaryResult 모델 파싱 (REQ-APP-040)

**Given** 백엔드가 다음 JSON을 반환할 때:
```json
{
  "summary_text": "회의 요약 내용",
  "action_items": [{"task": "리뷰", "priority": "high"}],
  "key_decisions": ["안건 1번 승인", "예산 확정"],
  "next_steps": ["팀 미팅 예약", "문서 업데이트"]
}
```
**When** Flutter 클라이언트가 `SummaryResult.fromJson()`으로 파싱하면
**Then** 모든 필드가 정확히 매핑되고, `keyDecisions`에 2개 항목, `nextSteps`에 2개 항목이 포함된다.

---

## AC-2: summaryResultProvider 타입 안전성 (REQ-APP-041)

**Given** `summaryResultProvider`가 API 응답을 파싱할 때
**When** 응답에 `key_decisions`와 `next_steps`가 포함되면
**Then** `SummaryResult` 객체로 반환되고, 문자열 키 기반 접근(`data['key']`) 없이 프로퍼티 접근(`result.keyDecisions`)으로 사용 가능하다.

---

## AC-3: 주요 결정 사항 표시 (REQ-APP-042)

**Given** 요약 결과에 key_decisions가 존재할 때
**When** 사용자가 'AI 요약' 탭을 선택하면
**Then** 요약 텍스트 아래에 "주요 결정 사항" 제목과 함께 번호 매기기 리스트가 표시된다.

**Given** key_decisions가 빈 배열일 때
**When** 사용자가 'AI 요약' 탭을 선택하면
**Then** "주요 결정 사항" 섹션은 표시되지 않는다.

---

## AC-4: 다음 단계 표시 (REQ-APP-043)

**Given** 요약 결과에 next_steps가 존재할 때
**When** 사용자가 'AI 요약' 탭을 선택하면
**Then** "다음 단계" 제목과 함께 번호 매기기 리스트가 표시된다.

**Given** next_steps가 빈 배열일 때
**When** 사용자가 'AI 요약' 탭을 선택하면
**Then** "다음 단계" 섹션은 표시되지 않는다.

---

## AC-5: API 서비스 테스트 커버리지 (REQ-APP-044)

**Given** SPEC-APP-004 변경사항이 적용된 후
**When** `flutter test` 전체 테스트를 실행하면
**Then** SummaryApi, MinutesApi, DiarizationApi 각각의 주요 메서드가 테스트되고, 전체 테스트가 통과한다.

---

## AC-6: 기존 기능 회귀 없음

**Given** SPEC-APP-004 변경사항이 적용된 후
**When** `flutter test` 전체 테스트를 실행하면
**Then** SPEC-APP-003의 액션 아이템 기능을 포함한 기존 테스트가 모두 통과한다.

---

## Quality Gates

- [ ] `dart analyze` 경고 0개 (신규)
- [ ] `flutter test` 전체 통과
- [ ] 기존 SPEC-APP-003 테스트 회귀 없음
- [ ] 런타임 타입 에러 없음
