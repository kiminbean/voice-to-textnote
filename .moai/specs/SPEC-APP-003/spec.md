---
id: SPEC-APP-003
version: "1.1.0"
status: completed
created: "2026-03-22"
updated: "2026-03-22"
author: kisoo
priority: high
issue_number: 0
---

## HISTORY

| Date | Version | Author | Change |
|------|---------|--------|--------|
| 2026-03-22 | 1.0.0 | kisoo | 초기 작성 |
| 2026-03-22 | 1.1.0 | kisoo | 구현 완료 (TDD 3 사이클, 93개 테스트 통과) |

---

# SPEC-APP-003: 액션 아이템 Flutter UI 구조화 표시

## 1. 개요

백엔드 AI 요약 API가 반환하는 구조화된 액션 아이템(assignee, task, deadline, priority)을 Flutter 클라이언트에서 올바르게 파싱하고 리치 UI로 표시한다.

### 현재 문제

- Flutter 클라이언트가 `action_items`를 `List<String>`으로 캐스팅하여 **런타임 에러 발생 가능**
- 담당자, 마감일, 우선순위 정보가 **UI에 표시되지 않음**
- 타입 안전성 없이 `Map<String, dynamic>` 원시 데이터를 직접 사용

### 범위

- **수정 대상**: Flutter 클라이언트만 (백엔드 변경 없음)
- **범위 외**: key_decisions/next_steps UI, 체크 상태 영속화, 알림 기능

---

## 2. EARS 요구사항

### REQ-APP-030: ActionItem Dart 모델 (Ubiquitous)

**The system shall** `ActionItem` Dart 모델 클래스를 제공하여 백엔드 API 응답의 액션 아이템 객체를 타입 안전하게 표현한다.

- 필드: `assignee` (String?), `task` (String), `deadline` (String?), `priority` (String, 기본값 "medium")
- 불변 객체 (freezed 또는 immutable class)
- `fromJson` 팩토리 생성자 제공

### REQ-APP-031: Provider 파싱 수정 (Ubiquitous)

**The system shall** `summaryResultProvider`와 `resultProvider`에서 `action_items` 필드를 `List<ActionItem>` 타입으로 올바르게 파싱한다.

- `cast<String>()` 호출 제거
- `Map<String, dynamic>` → `ActionItem.fromJson()` 변환
- 파싱 실패 시 빈 리스트 반환 (graceful 처리)

### REQ-APP-032: 액션 아이템 카드 UI (Ubiquitous)

**The system shall** 각 액션 아이템을 담당자, 작업 내용, 마감일, 우선순위를 포함하는 카드 위젯으로 표시한다.

- 체크박스 + 작업 내용 (기존 기능 유지)
- 담당자 이름 표시 (없으면 "미지정")
- 마감일 표시 (없으면 미표시)
- 우선순위 배지: high(빨강), medium(주황), low(초록)

### REQ-APP-033: 우선순위 필터링 (Event-Driven)

**When** 사용자가 우선순위 필터 칩을 탭하면, **the system shall** 해당 우선순위의 액션 아이템만 필터링하여 표시한다.

- 필터 칩: 전체, High, Medium, Low
- 기본값: 전체
- 필터 변경 시 즉시 반영 (애니메이션)

### REQ-APP-034: 빈 상태 및 에러 처리 (State-Driven)

**While** 액션 아이템이 없는 상태이면, **the system shall** 기존 EmptyStateWidget과 동일한 스타일의 빈 상태 화면을 표시한다.

**While** API 호출이 실패한 상태이면, **the system shall** 기존 ErrorRetryWidget으로 재시도 옵션을 제공한다.

---

## 3. 수정 대상 파일

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `client/lib/models/action_item.dart` | 신규 | ActionItem 모델 클래스 |
| `client/lib/providers/result_provider.dart` | 수정 | ActionItem 파싱 로직 |
| `client/lib/screens/result_screen.dart` | 수정 | 액션 아이템 카드 UI |
| `client/test/models/action_item_test.dart` | 신규 | 모델 단위 테스트 |
| `client/test/providers/result_provider_test.dart` | 수정 | 파싱 테스트 업데이트 |
| `client/test/screens/result_screen_test.dart` | 신규/수정 | UI 위젯 테스트 |

---

## 4. 기술 제약

- Flutter 3.24+ / Dart 3.5+
- Riverpod 상태 관리 패턴 유지
- 기존 위젯 (EmptyStateWidget, ErrorRetryWidget, ShimmerText) 재사용
- 백엔드 API 변경 없음 — 클라이언트 전용 수정

---

## 5. Implementation Notes

### 구현 결과 (2026-03-22)

**개발 방법론**: TDD (RED-GREEN-REFACTOR) 3 사이클

**변경 파일 (6개)**:
| 파일 | 변경 | 라인 |
|------|------|------|
| `client/lib/models/action_item.dart` | 신규 | +47 |
| `client/lib/providers/result_provider.dart` | 수정 | +10/-6 |
| `client/lib/screens/result_screen.dart` | 수정 | +201/-45 |
| `client/test/models/action_item_test.dart` | 신규 | +139 |
| `client/test/providers/result_provider_test.dart` | 수정 | +95/-1 |
| `client/test/screens/result_screen_test.dart` | 신규 | +325 |

**테스트 결과**: 93/93 전체 통과
**dart analyze**: 신규 경고 0개
**신규 의존성**: 없음 (기존 스택 유지)

**핵심 변경 사항**:
- `ActionItem` 불변 모델 클래스 (freezed 미사용, 수동 구현)
- `.cast<String>()` 버그 2곳 수정 → `.whereType<Map>().map(ActionItem.fromJson)`
- `_ActionItemsTab` → `ConsumerStatefulWidget` 변환 (필터 상태 관리)
- 우선순위 필터 칩 (전체/High/Medium/Low)
- 리치 카드 UI (담당자/마감일/우선순위 배지)

**범위 이탈**: 없음 (SPEC 범위 내 정확히 구현)
