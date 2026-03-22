# SPEC-TMPL-001 Implementation Plan

## Development Mode: TDD (RED-GREEN-REFACTOR)

## 영향 도메인: Backend (Python) + Frontend (Flutter) — 2개 도메인

---

## Phase 1: Backend — 템플릿 파서 모듈 (REQ-TMPL-002)

### RED
- `backend/tests/unit/test_template_parser.py` 작성
  - DOCX 파일에서 섹션/필드 추출 테스트
  - PDF 파일에서 섹션/표 추출 테스트
  - 빈 파일 graceful 처리 테스트
  - 지원 안 되는 형식 예외 테스트

### GREEN
- `backend/pipeline/template_parser.py` 생성
  - `TemplateParser.extract_structure(file_path) -> dict`
  - `_parse_docx()`: python-docx Heading + Table + Paragraph
  - `_parse_pdf()`: pdfplumber text + tables
  - 추출 실패 시 raw_text fallback

### REFACTOR
- 공통 섹션 감지 로직 추출

---

## Phase 2: Backend — 템플릿 API + 스키마 (REQ-TMPL-001, REQ-TMPL-003)

### RED
- `backend/tests/integration/test_template_api.py` 작성
  - POST 업로드 테스트 (DOCX, PDF)
  - GET 목록 테스트
  - GET 상세 테스트
  - DELETE 테스트
  - 잘못된 형식 거부 테스트

### GREEN
- `backend/schemas/template.py` 생성 — TemplateUploadResponse, TemplateListItem, TemplateDetail
- `backend/app/api/v1/templates.py` 생성 — CRUD 라우터
- `backend/app/config.py` 수정 — templates_dir 추가
- `backend/app/main.py` 수정 — templates 라우터 등록
- `deploy/requirements-ubuntu.txt` 수정 — pdfplumber, python-docx 추가

### REFACTOR
- Redis 키 네이밍 일관성 정리

---

## Phase 3: Backend — 프롬프트 확장 (REQ-TMPL-004)

### RED
- `backend/tests/unit/test_summary_generator.py` 수정
  - template_structure가 있을 때 프롬프트에 양식 지시문 포함 테스트
  - template_structure가 None일 때 기존 프롬프트 유지 테스트

### GREEN
- `backend/schemas/summary.py` 수정 — SummaryCreateRequest에 template_id 추가
- `backend/pipeline/summary_generator.py` 수정 — build_prompt에 template_structure 파라미터 추가
- `backend/workers/tasks/summary_task.py` 수정 — template_id 전달
- `backend/app/api/v1/summary.py` 수정 — template_id 전달

### REFACTOR
- 하위 호환성 검증

---

## Phase 4: Flutter — 템플릿 모델 + API 서비스 (REQ-TMPL-005)

### RED
- `client/test/services/template_api_test.dart` 작성

### GREEN
- `client/lib/models/template.dart` 생성
- `client/lib/services/template_api.dart` 생성
- `client/lib/providers/template_provider.dart` 생성
- `client/pubspec.yaml` 수정 — file_picker 추가

### REFACTOR
- 기존 API 패턴과 일관성 확인

---

## Phase 5: Flutter — 템플릿 관리 화면 + 선택 UI (REQ-TMPL-005, REQ-TMPL-006)

### RED
- 위젯 테스트 작성 (template_screen, home_screen 수정)

### GREEN
- `client/lib/screens/template_screen.dart` 생성 — 목록/업로드/삭제
- `client/lib/screens/home_screen.dart` 수정 — AppBar에 템플릿 아이콘 추가
- `client/lib/screens/processing_screen.dart` 수정 — 템플릿 선택 UI
- `client/lib/config/router.dart` 수정 — /templates 라우트 추가

### REFACTOR
- 위젯 분리 정리

---

## Phase 6: 통합 검증

- Backend: `pytest` 전체 통과
- Flutter: `flutter test` 전체 통과
- `dart analyze` 경고 0개
- 서버 배포: `pip install pdfplumber python-docx`
- E2E: 양식 업로드 → 요약 생성 → 양식 기반 결과 확인

---

## Risk Analysis

| 리스크 | 확률 | 대응 |
|--------|------|------|
| DOCX 구조 추출 부정확 | 중간 | raw_text fallback + AI 보조 추출 |
| PDF 표 추출 어려움 | 중간 | pdfplumber의 extract_tables() 활용 |
| file_picker iOS 권한 문제 | 낮음 | Info.plist에 파일 접근 권한 추가 |
| 프롬프트 길이 초과 | 낮음 | 구조 요약 시 섹션명만 주입 (상세 제외) |

## Dependencies

- `pdfplumber`, `python-docx` (Backend)
- `file_picker: ^8.0.0` (Flutter)
- 기존 UploadFile 패턴 재사용
- 기존 Redis 캐싱 패턴 재사용
