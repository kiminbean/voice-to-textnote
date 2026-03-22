---
id: SPEC-EXPORT-001
type: plan
development_mode: tdd
created: "2026-03-22"
updated: "2026-03-22"
author: kisoo
---

# SPEC-EXPORT-001: 구현 계획 (Implementation Plan)

## 개발 방법론: TDD (Test-Driven Development)

각 Phase는 RED -> GREEN -> REFACTOR 사이클로 진행한다.

---

## Phase 1: Backend PDF Generator (Primary Goal)

**목표**: fpdf2 기반 PDF 생성 모듈 구현

### RED (실패하는 테스트 작성)

- `tests/test_pdf_generator.py` 생성
- 테스트 케이스:
  - `test_generate_pdf_returns_bytes`: PDF 생성 시 bytes 반환 확인
  - `test_pdf_contains_header_section`: 헤더 섹션(제목, 날짜) 포함 확인
  - `test_pdf_contains_speaker_stats`: 발화자 통계 테이블 포함 확인
  - `test_pdf_contains_minutes_body`: 회의록 본문 포함 확인
  - `test_pdf_contains_summary`: 요약 섹션 포함 확인
  - `test_pdf_contains_action_items`: 액션 아이템 테이블 포함 확인
  - `test_korean_text_rendering`: 한국어 텍스트 정상 렌더링 확인
  - `test_empty_segments_raises_error`: 빈 segments 시 예외 발생 확인

### GREEN (테스트 통과하는 최소 구현)

- `backend/pipeline/pdf_generator.py` 구현
  - `MinutesPDFGenerator` 클래스 생성
  - NotoSansKR 폰트 등록 (`backend/assets/fonts/`)
  - 섹션별 렌더링 메서드: `_render_header()`, `_render_speaker_stats()`, `_render_minutes_body()`, `_render_summary()`, `_render_key_decisions()`, `_render_action_items()`
  - `generate(minutes_data: dict) -> bytes` 메인 메서드
  - BytesIO를 사용한 메모리 내 PDF 생성

### REFACTOR

- 공통 스타일 상수 추출 (폰트 크기, 여백, 색상)
- 섹션 렌더링 메서드 일관성 확보
- 에러 메시지 한국어/영어 분리

### 의존성

- fpdf2 패키지 설치
- NotoSansKR 폰트 파일 다운로드 및 배치

---

## Phase 2: Backend Export API + Schemas (Primary Goal)

**목표**: Export API 엔드포인트 및 스키마 구현

### RED

- `tests/test_export_api.py` 생성
- 테스트 케이스:
  - `test_export_pdf_success`: 유효한 task_id로 PDF 반환 확인 (200, application/pdf)
  - `test_export_pdf_not_found`: 존재하지 않는 task_id로 404 반환 확인
  - `test_export_pdf_incomplete_data`: 불완전한 데이터로 422 반환 확인
  - `test_export_pdf_content_disposition`: 응답 헤더 Content-Disposition 확인
  - `test_export_pdf_content_type`: Content-Type이 application/pdf인지 확인

### GREEN

- `backend/schemas/export.py` 구현
  - `ExportErrorResponse` 스키마
- `backend/app/api/v1/export.py` 구현
  - `GET /api/v1/export/pdf/{minutes_task_id}` 엔드포인트
  - Redis에서 minutes 데이터 조회 (TTL 만료 시 SQLite fallback)
  - `MinutesPDFGenerator`를 호출하여 PDF 생성
  - `StreamingResponse`로 PDF 반환
- `backend/app/main.py` 수정
  - Export 라우터 등록

### REFACTOR

- Redis/SQLite 데이터 조회 로직을 서비스 레이어로 분리 검토
- 에러 응답 형식 기존 API와 일관성 확보

### 의존성

- Phase 1 완료 필수 (PDF Generator)
- `pyproject.toml`, `deploy/requirements-ubuntu.txt`에 fpdf2 추가

---

## Phase 3: Flutter Export Service + UI (Secondary Goal)

**목표**: Flutter 앱에 내보내기 기능 추가

### RED

- `client/test/services/export_api_test.dart` 생성
- 테스트 케이스:
  - `test_export_api_download_pdf`: API 호출 및 파일 저장 확인
  - `test_export_api_error_handling`: 에러 응답 처리 확인
- `client/test/screens/result_screen_test.dart` 수정
  - `test_export_button_exists`: 내보내기 버튼 존재 확인
  - `test_export_button_triggers_download`: 버튼 탭 시 다운로드 동작 확인

### GREEN

- `client/lib/services/export_api.dart` 구현
  - `ExportApiService` 클래스
  - `downloadPdf(String taskId) -> File`: Dio로 PDF 다운로드
  - 임시 디렉토리에 파일 저장
- `client/lib/screens/result_screen.dart` 수정
  - AppBar에 내보내기 아이콘 버튼 추가
  - 다운로드 중 CircularProgressIndicator 표시
  - 다운로드 완료 후 share_plus로 공유 시트 호출
  - 실패 시 SnackBar 오류 메시지 표시
- `client/pubspec.yaml` 수정
  - share_plus 패키지 추가

### REFACTOR

- 로딩 상태 관리 패턴 기존 앱과 일관성 확보
- 에러 핸들링 공통 패턴 적용

### 의존성

- Phase 2 완료 필수 (Export API)
- Dio 패키지 (기존 사용 중)
- share_plus 패키지 신규 추가

---

## Phase 4: 통합 검증 (Secondary Goal)

**목표**: 전체 파이프라인 End-to-End 검증

### 검증 항목

- Backend 단독 테스트:
  - `pytest tests/test_pdf_generator.py tests/test_export_api.py -v`
  - curl로 Export API 직접 호출하여 PDF 다운로드 확인
  - PDF 파일 열어서 한국어 렌더링 확인
- Flutter 통합 테스트:
  - ResultScreen에서 내보내기 버튼 탭
  - PDF 다운로드 및 iOS Share Sheet 동작 확인
- 엣지 케이스 검증:
  - Redis TTL 만료 후 SQLite fallback 동작 확인
  - 빈 segments 데이터로 422 응답 확인
  - 네트워크 오류 시 Flutter 에러 처리 확인

---

## 리스크 분석 (Risk Analysis)

| 리스크                                | 확률 | 영향도 | 대응 전략                                           |
| ------------------------------------- | ---- | ------ | --------------------------------------------------- |
| NotoSansKR 폰트 파일 크기 (4MB+)     | 중간 | 중간   | Regular + Bold만 포함, 서버 빌드 시 다운로드         |
| fpdf2 한국어 줄바꿈 이슈             | 중간 | 높음   | multi_cell 사용, 긴 텍스트 사전 처리                |
| Redis TTL 만료 시 데이터 유실         | 낮음 | 높음   | SQLite fallback 로직 구현                           |
| PDF 생성 시간이 긴 회의록 (1시간+)   | 낮음 | 중간   | MVP에서는 동기 처리, Phase 2에서 Celery 전환 검토   |
| iOS 시뮬레이터에서 share_plus 제한   | 높음 | 낮음   | 실기기 테스트로 검증, 시뮬레이터에서는 파일 저장만   |

---

## 의존성 (Dependencies)

| 패키지       | 버전       | 용도                        | 설치 위치                      |
| ------------ | ---------- | --------------------------- | ------------------------------ |
| fpdf2        | >= 2.8.1   | PDF 생성                    | pyproject.toml, requirements   |
| NotoSansKR   | -          | 한국어 폰트 (TTF)           | backend/assets/fonts/          |
| share_plus   | >= 10.0.0  | iOS Share Sheet             | client/pubspec.yaml            |
| Dio          | (기존)     | HTTP 클라이언트             | client/pubspec.yaml (기존)     |

---

## 추적성 태그 (Traceability)

- **SPEC**: SPEC-EXPORT-001
- **Phase 1**: REQ-EXPORT-002, REQ-EXPORT-003
- **Phase 2**: REQ-EXPORT-001, REQ-EXPORT-005
- **Phase 3**: REQ-EXPORT-004, REQ-EXPORT-005
- **Phase 4**: 전체 요구사항 통합 검증
