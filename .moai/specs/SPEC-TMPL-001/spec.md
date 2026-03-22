---
id: SPEC-TMPL-001
version: "1.0.0"
status: draft
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

---

# SPEC-TMPL-001: 회의록 양식 업로드 + 양식 기반 회의록 생성 (MVP)

## 1. 개요

사용자가 회의록 양식 파일(PDF, DOCX)을 업로드하면 양식의 구조를 추출하고, AI 요약 생성 시 해당 양식에 맞춰 회의록을 작성한다. 양식이 없으면 기본 양식(현재 4개 항목)으로 생성한다.

### 현재 상태

- AI 요약은 하드코딩된 4개 항목(summary_text, action_items, key_decisions, next_steps)만 생성
- 사용자 정의 양식 업로드/관리 기능 없음
- 양식 기반 회의록 커스터마이징 불가

### 범위

- **포함**: PDF/DOCX 양식 업로드, 구조 추출, 양식 기반 AI 프롬프트, Flutter 템플릿 관리 UI
- **범위 외**: XLSX/XLS/HWP 파싱 (2차), 양식 편집/미리보기 (2차), 양식 공유

---

## 2. EARS 요구사항

### REQ-TMPL-001: 템플릿 파일 업로드 API (Ubiquitous)

**The system shall** PDF 또는 DOCX 형식의 회의록 양식 파일을 업로드받아 저장하고 구조를 추출한다.

- POST /api/v1/templates (multipart/form-data)
- 지원 형식: .pdf, .docx (확장자 검증)
- 파일 크기 제한: 10MB
- 원본 파일 보존: `storage/templates/{template_id}/original.{ext}`
- 구조 추출 결과 JSON 저장: `storage/templates/{template_id}/structure.json`
- Redis에 메타데이터 저장 (template:{template_id})

### REQ-TMPL-002: 템플릿 구조 추출 (Ubiquitous)

**The system shall** 업로드된 파일에서 회의록 양식 구조(섹션 제목, 필드명, 표 여부)를 추출한다.

- DOCX: python-docx로 Heading 스타일 섹션 + 표 + 필드 추출
- PDF: pdfplumber로 텍스트 + 표 추출, 폰트 크기/볼드로 섹션 경계 감지
- 추출 실패 시: 원본 텍스트 처음 1000자를 raw_text로 반환 (graceful 처리)

### REQ-TMPL-003: 템플릿 목록/조회/삭제 API (Ubiquitous)

**The system shall** 저장된 템플릿의 CRUD 기능을 제공한다.

- GET /api/v1/templates — 전체 목록 반환 (id, name, format, created_at)
- GET /api/v1/templates/{template_id} — 메타데이터 + 추출된 구조 반환
- DELETE /api/v1/templates/{template_id} — 파일 + Redis 데이터 삭제

### REQ-TMPL-004: 양식 기반 AI 프롬프트 확장 (Event-Driven)

**When** 요약 생성 요청에 template_id가 포함되면, **the system shall** 해당 템플릿 구조를 AI 프롬프트에 주입하여 양식에 맞춘 회의록을 생성한다.

- SummaryCreateRequest에 `template_id: str | None = None` 추가
- template_id가 있으면: Redis에서 구조 로드 → 프롬프트에 "다음 양식 구조에 맞춰 작성" 지시문 추가
- template_id가 없으면: 기존 기본 4개 항목 유지 (하위 호환)
- Celery 태스크에 template_id 전달

### REQ-TMPL-005: Flutter 템플릿 관리 화면 (Ubiquitous)

**The system shall** 회의록 양식을 업로드/목록/삭제할 수 있는 Flutter 화면을 제공한다.

- 홈 화면 AppBar에 템플릿 관리 아이콘 추가
- 템플릿 목록: 이름, 형식, 업로드일 표시
- 업로드: file_picker로 PDF/DOCX 선택 → API 업로드
- 삭제: 스와이프 또는 삭제 버튼

### REQ-TMPL-006: 요약 생성 시 템플릿 선택 (Event-Driven)

**When** 사용자가 녹음 완료 후 처리를 시작하면, **the system shall** 저장된 템플릿 중 하나를 선택하거나 기본 양식을 사용할 수 있는 옵션을 제공한다.

- processing_screen에서 요약 시작 전 템플릿 선택 드롭다운/바텀시트
- "기본 양식" 옵션 항상 포함 (template_id = null)
- 선택된 template_id를 POST /summaries 요청에 포함

### REQ-TMPL-007: 양식 기반 결과 표시 (State-Driven)

**While** 양식 기반 요약이 완료된 상태이면, **the system shall** AI 요약 탭에서 양식의 섹션 구조에 맞춰 결과를 표시한다.

- template_id가 있는 요약: 섹션별로 구분하여 표시
- template_id가 없는 요약: 기존 표시 방식 유지 (하위 호환)

---

## 3. 수정 대상 파일

### Backend (신규 6개 + 수정 4개)

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `backend/app/api/v1/templates.py` | 신규 | 템플릿 CRUD API 라우터 |
| `backend/pipeline/template_parser.py` | 신규 | DOCX/PDF 구조 추출 파서 |
| `backend/schemas/template.py` | 신규 | 템플릿 요청/응답 스키마 |
| `backend/tests/unit/test_template_parser.py` | 신규 | 파서 단위 테스트 |
| `backend/tests/integration/test_template_api.py` | 신규 | API 통합 테스트 |
| `backend/tests/fixtures/` | 신규 | 테스트용 샘플 PDF/DOCX 파일 |
| `backend/schemas/summary.py` | 수정 | SummaryCreateRequest에 template_id 추가 |
| `backend/pipeline/summary_generator.py` | 수정 | build_prompt에 template 지시문 주입 |
| `backend/workers/tasks/summary_task.py` | 수정 | template_id 전달 로직 |
| `backend/app/config.py` | 수정 | templates_dir 설정 추가 |
| `deploy/requirements-ubuntu.txt` | 수정 | pdfplumber, python-docx 추가 |

### Flutter (신규 5개 + 수정 3개)

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `client/lib/services/template_api.dart` | 신규 | 템플릿 CRUD API 서비스 |
| `client/lib/models/template.dart` | 신규 | 템플릿 모델 |
| `client/lib/providers/template_provider.dart` | 신규 | 템플릿 목록/선택 상태 관리 |
| `client/lib/screens/template_screen.dart` | 신규 | 템플릿 관리 화면 |
| `client/test/services/template_api_test.dart` | 신규 | API 서비스 테스트 |
| `client/lib/screens/home_screen.dart` | 수정 | 템플릿 관리 진입점 추가 |
| `client/lib/screens/processing_screen.dart` | 수정 | 템플릿 선택 UI 추가 |
| `client/pubspec.yaml` | 수정 | file_picker 패키지 추가 |

---

## 4. 기술 제약

- Python 3.11+ / FastAPI / Celery / Redis
- Flutter 3.24+ / Dart 3.5+ / Riverpod
- 신규 의존성: `pdfplumber`, `python-docx` (Backend), `file_picker` (Flutter)
- 파일 저장소: `storage/templates/` (서버 로컬 디스크)
- 파일 크기 제한: 10MB
- 지원 형식 (MVP): PDF, DOCX만
