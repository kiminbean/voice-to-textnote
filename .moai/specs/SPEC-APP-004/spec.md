---
id: SPEC-APP-004
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
| 2026-03-22 | 1.1.0 | kisoo | 구현 완료 (TDD 5 사이클, 120개 테스트 통과) |

---

# SPEC-APP-004: Summary 결과 화면 완성도 개선

## 1. 개요

백엔드 AI 요약 API가 반환하는 `key_decisions`(주요 결정 사항)과 `next_steps`(다음 단계) 필드를 Flutter 클라이언트에서 표시하고, `summaryResultProvider`를 타입 안전한 모델로 전환한다.

### 현재 문제

- `_SummaryTab`이 `summary_text`만 표시하고 **key_decisions/next_steps를 완전히 무시**
- `summaryResultProvider`가 `Map<String, dynamic>` 원시 반환 → **타입 안전성 없음**
- `MeetingResult`에 `key_decisions`/`next_steps` 필드 누락
- `SummaryApi`, `MinutesApi`, `DiarizationApi` **단위 테스트 없음**

### 범위

- **수정 대상**: Flutter 클라이언트만 (백엔드 변경 없음)
- **범위 외**: API 에러 핸들링 체계화 (별도 SPEC), freezed 마이그레이션 (별도 SPEC), i18n

---

## 2. EARS 요구사항

### REQ-APP-040: SummaryResult Dart 모델 (Ubiquitous)

**The system shall** `SummaryResult` Dart 모델 클래스를 제공하여 백엔드 요약 API 응답을 타입 안전하게 표현한다.

- 필드: `summaryText` (String), `actionItems` (List<ActionItem>), `keyDecisions` (List<String>), `nextSteps` (List<String>)
- 불변 객체, `fromJson` 팩토리 생성자 제공
- 누락 필드에 대해 빈 리스트/빈 문자열 기본값 적용

### REQ-APP-041: summaryResultProvider 타입 변환 (Ubiquitous)

**The system shall** `summaryResultProvider`의 반환 타입을 `Map<String, dynamic>`에서 `SummaryResult`로 변경한다.

- `SummaryResult.fromJson()`을 통한 타입 안전 파싱
- 기존 `_SummaryTab`, `_ActionItemsTab`의 참조 코드를 타입 안전 접근으로 수정
- `MeetingResult`에 `keyDecisions` (List<String>)과 `nextSteps` (List<String>) 필드 추가
- `resultProvider`에서도 해당 필드 파싱

### REQ-APP-042: 주요 결정 사항 UI (Ubiquitous)

**The system shall** AI 요약 탭에 주요 결정 사항(key_decisions) 섹션을 표시한다.

- 요약 텍스트 아래에 "주요 결정 사항" 섹션 추가
- 각 항목을 번호 매기기 리스트로 표시
- 항목이 없으면 섹션 자체를 숨김

### REQ-APP-043: 다음 단계 UI (Ubiquitous)

**The system shall** AI 요약 탭에 다음 단계(next_steps) 섹션을 표시한다.

- 주요 결정 사항 아래에 "다음 단계" 섹션 추가
- 각 항목을 번호 매기기 리스트로 표시
- 항목이 없으면 섹션 자체를 숨김

### REQ-APP-044: API 서비스 테스트 보완 (Ubiquitous)

**The system shall** `SummaryApi`, `MinutesApi`, `DiarizationApi` 서비스에 대한 단위 테스트를 제공한다.

- 각 서비스의 주요 메서드 테스트 (create, getStatus, getResult, delete)
- 기존 `health_api_test.dart` 패턴 참고
- mocktail로 Dio 모킹

---

## 3. 수정 대상 파일

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `client/lib/models/summary_result.dart` | 신규 | SummaryResult 모델 클래스 |
| `client/lib/providers/result_provider.dart` | 수정 | summaryResultProvider 타입 변환 + MeetingResult 확장 |
| `client/lib/screens/result_screen.dart` | 수정 | _SummaryTab에 key_decisions/next_steps 섹션 추가 |
| `client/test/models/summary_result_test.dart` | 신규 | SummaryResult 모델 테스트 |
| `client/test/providers/result_provider_test.dart` | 수정 | 타입 변환 테스트 업데이트 |
| `client/test/services/summary_api_test.dart` | 신규 | SummaryApi 테스트 |
| `client/test/services/minutes_api_test.dart` | 신규 | MinutesApi 테스트 |
| `client/test/services/diarization_api_test.dart` | 신규 | DiarizationApi 테스트 |

---

## 4. 기술 제약

- Flutter 3.24+ / Dart 3.5+
- Riverpod 상태 관리 패턴 유지
- 기존 위젯 재사용
- 백엔드 API 변경 없음 — 클라이언트 전용 수정
- ActionItem 모델은 SPEC-APP-003에서 이미 구현됨 — 재사용
