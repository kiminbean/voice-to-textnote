# SPEC-UI-001: 동적 회의록 테이블 UI

---
id: SPEC-UI-001
title: Dynamic Minutes Table UI
created: 2026-03-25
status: Planned
priority: High (P1)
domain: UI
issue_number: 0
---

## 1. 문제 정의

현재 "회의록" 탭의 테이블 레이아웃(과정명/프로젝트명/팀명/작성자/참석자/회의안건/회의내용/결정된 사안)이 Flutter 코드에 **하드코딩**되어 있다. 사용자가 다른 형태의 PDF 양식을 업로드해도 동일한 7행 테이블이 표시된다.

## 2. 목표

업로드한 양식의 구조(섹션, 필드)에 맞춰 "회의록" 탭의 테이블 레이아웃을 **동적으로 생성**한다.

## 3. 요구사항

### REQ-UI-001: 양식 구조를 요약 결과에 포함 (Backend)

**WHEN** AI 요약이 생성되고 양식이 선택되었을 때, **THEN** 요약 결과 JSON에 `template_structure` 필드를 포함해야 한다.

- summary_task의 final_result에 `template_structure` 추가
- 양식 없이 생성된 경우 `template_structure: null`
- 기존 API 응답과 하위 호환성 유지

### REQ-UI-002: Flutter에서 양식 구조 기반 동적 테이블 렌더링

**WHEN** 회의록 탭이 표시될 때, **THEN** template_structure가 존재하면 해당 구조의 섹션 목록으로 테이블 행을 동적 생성하고, 존재하지 않으면 기본 테이블(현재 하드코딩)을 표시해야 한다.

- `template_structure.sections`의 각 항목 → 테이블 1행
- `template_structure.has_table == true`이면 테이블 UI, false이면 섹션 목록 UI
- `template_structure.raw_text_preview`에서 필드 라벨 추출

### REQ-UI-003: AI 프롬프트에 섹션별 개별 출력 지시

**WHEN** 양식이 선택된 요약을 생성할 때, **THEN** AI에게 각 섹션별 내용을 개별 JSON 필드로 출력하도록 지시해야 한다.

- 현재: `summary_text` 하나에 모든 내용 통합
- 개선: `sections: {"회의안건": "...", "회의내용": "...", "결정된 사안": "..."}` 형태
- Flutter에서 각 섹션을 테이블 행의 내용으로 매핑

### REQ-UI-004: 양식 미선택 시 기본 테이블 유지

시스템은 **항상** 양식이 선택되지 않은 경우 현재의 하드코딩된 기본 테이블을 표시해야 한다.

- 하위 호환성 보장
- 기존 결과 데이터에 template_structure가 없어도 정상 동작

## 4. 명세

### 4.1 Backend 변경 (summary_task.py)

```
final_result에 추가:
  "template_structure": template_structure  # 양식 구조 dict 또는 null
```

### 4.2 AI 프롬프트 변경 (summary_generator.py)

양식이 있을 때 JSON 출력 형식:
```json
{
  "summary_text": "전체 요약",
  "sections": {
    "회의안건": "양식 섹션 1의 내용",
    "회의내용": "양식 섹션 2의 내용",
    "결정된 사안": "양식 섹션 3의 내용"
  },
  "action_items": [...],
  "key_decisions": [...],
  "next_steps": [...]
}
```

### 4.3 Flutter 변경 (_MinutesTab)

```
if template_structure != null:
  섹션 목록 기반 동적 테이블 생성
  각 section.title → 라벨 셀
  result.sections[title] → 내용 셀
else:
  기본 하드코딩 테이블 (현재 UI)
```

### 4.4 SummaryResult 모델 변경

Flutter `SummaryResult`에 추가:
- `Map<String, String>? sections` - 섹션별 내용
- `Map<String, dynamic>? templateStructure` - 양식 구조 정보

## 5. 제약사항

- 양식 구조의 섹션 수는 최대 20개로 제한
- 양식 없이 생성된 기존 결과와 하위 호환성 필수
- PDF 양식의 테이블 구조 인식은 pdfplumber 기반 (완벽하지 않을 수 있음)
