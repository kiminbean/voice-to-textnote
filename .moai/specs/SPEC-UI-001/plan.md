# SPEC-UI-001: 구현 계획

## Phase 1: Backend — 양식 구조 전달 + 섹션별 AI 출력

### Task 1.1: summary_task에 template_structure 포함 (REQ-UI-001)
- **파일**: `backend/workers/tasks/summary_task.py`
- **작업**: `final_result`에 `template_structure` 필드 추가
- **예상 시간**: 10분

### Task 1.2: AI 프롬프트에 섹션별 개별 출력 지시 (REQ-UI-003)
- **파일**: `backend/pipeline/summary_generator.py`
- **작업**:
  1. 양식 있을 때 JSON 출력에 `sections` 필드 추가 지시
  2. `parse_response()`에서 `sections` 파싱
- **예상 시간**: 30분

### Task 1.3: Backend SummaryResult 스키마 확장
- **파일**: `backend/schemas/summary.py`
- **작업**: `SummaryResult`에 `sections: dict[str, str]` 필드 추가
- **예상 시간**: 10분

## Phase 2: Flutter — 동적 테이블 렌더링

### Task 2.1: Flutter SummaryResult 모델 확장 (REQ-UI-002)
- **파일**: `client/lib/models/summary_result.dart`
- **작업**: `sections`, `templateStructure` 필드 추가 + fromJson 파싱
- **예상 시간**: 20분

### Task 2.2: _MinutesTab 동적 테이블 구현 (REQ-UI-002)
- **파일**: `client/lib/screens/result_screen.dart`
- **작업**:
  1. `templateStructure != null` 분기 추가
  2. `sections` 기반 동적 행 생성
  3. 기존 하드코딩 테이블은 else 분기로 유지 (REQ-UI-004)
- **예상 시간**: 1시간

## 의존성

```
Task 1.1 (template_structure 전달) ─── 독립
Task 1.2 (AI 프롬프트) ─── 독립
Task 1.3 (스키마) ─── 독립
  └── Task 2.1 (Flutter 모델) ─── Phase 1 완료 후
      └── Task 2.2 (동적 UI) ─── Task 2.1 완료 후
```
