# SPEC-TMPL-001 Acceptance Criteria

---

## AC-1: DOCX 템플릿 업로드 + 구조 추출 (REQ-TMPL-001, REQ-TMPL-002)

**Given** 회의록 양식이 포함된 DOCX 파일이 있을 때
**When** POST /api/v1/templates로 업로드하면
**Then** 파일이 저장되고, 섹션 목록(sections)과 필드명(fields)이 추출된 구조가 반환된다.

---

## AC-2: PDF 템플릿 업로드 + 구조 추출 (REQ-TMPL-001, REQ-TMPL-002)

**Given** 회의록 양식이 포함된 PDF 파일이 있을 때
**When** POST /api/v1/templates로 업로드하면
**Then** 파일이 저장되고, 텍스트 기반 섹션과 표 구조가 추출되어 반환된다.

---

## AC-3: 잘못된 형식 업로드 거부 (REQ-TMPL-001)

**Given** .xlsx 또는 .hwp 형식의 파일이 업로드될 때
**When** POST /api/v1/templates로 업로드하면
**Then** 400 Bad Request와 함께 "지원하지 않는 형식" 에러 메시지가 반환된다.

---

## AC-4: 템플릿 목록/조회/삭제 (REQ-TMPL-003)

**Given** 템플릿이 업로드된 상태에서
**When** GET /api/v1/templates를 호출하면
**Then** 저장된 템플릿 목록(id, name, format, created_at)이 반환된다.

**When** DELETE /api/v1/templates/{id}를 호출하면
**Then** 해당 템플릿 파일과 Redis 데이터가 삭제된다.

---

## AC-5: 양식 기반 AI 요약 생성 (REQ-TMPL-004)

**Given** 템플릿이 저장된 상태에서
**When** POST /api/v1/summaries에 template_id를 포함하여 요청하면
**Then** AI가 해당 양식 구조에 맞춘 회의록을 생성한다.

**When** template_id 없이 요청하면
**Then** 기존 기본 4개 항목(summary_text, action_items, key_decisions, next_steps)으로 생성된다.

---

## AC-6: Flutter 템플릿 관리 화면 (REQ-TMPL-005)

**Given** 앱이 실행된 상태에서
**When** 사용자가 홈 화면의 템플릿 관리 아이콘을 탭하면
**Then** 저장된 템플릿 목록이 표시되고, 업로드/삭제가 가능하다.

---

## AC-7: 요약 시 템플릿 선택 (REQ-TMPL-006)

**Given** 녹음이 완료되어 처리 시작 단계에서
**When** 사용자가 요약 생성을 시작하면
**Then** 저장된 템플릿 중 하나를 선택하거나 "기본 양식"을 선택할 수 있다.

---

## AC-8: 기존 기능 회귀 없음

**Given** SPEC-TMPL-001 변경사항이 적용된 후
**When** template_id 없이 기존 방식으로 요약을 생성하면
**Then** 기존과 동일한 결과가 반환되고, 기존 테스트가 모두 통과한다.

---

## Quality Gates

- [ ] Backend: `pytest` 전체 통과
- [ ] Flutter: `flutter test` 전체 통과
- [ ] `dart analyze` 경고 0개 (신규)
- [ ] 하위 호환: template_id 없는 요청이 기존과 동일하게 작동
