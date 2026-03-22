---
id: SPEC-EXPORT-001
version: "1.0.0"
status: draft
created: "2026-03-22"
updated: "2026-03-22"
author: kisoo
priority: medium
issue_number: 0
---

# SPEC-EXPORT-001: 회의록 PDF 내보내기

## 변경 이력 (HISTORY)

| 버전  | 날짜       | 작성자 | 변경 내용           |
| ----- | ---------- | ------ | ------------------- |
| 1.0.0 | 2026-03-22 | kisoo  | 최초 SPEC 작성      |

---

## 1. 개요 (Overview)

### 1.1 현재 상태

- 회의 결과는 Redis(24시간 TTL) + SQLite DB(best-effort persist)에 저장
- 회의록: segments[{speaker_name, text, start, end}], speakers 통계, markdown
- 요약: summary_text, action_items[{assignee, task, deadline, priority}], key_decisions[], next_steps[]
- Flutter 결과 화면: 3개 탭(회의록, 요약, 액션 아이템) 제공
- PDF 내보내기 기능 없음
- 파일 다운로드 엔드포인트 없음

### 1.2 범위 (Scope)

- Backend: fpdf2를 사용한 PDF 생성 (동기 처리, MVP 단계에서 Celery 불필요)
- Backend: PDF를 StreamingResponse로 반환하는 Export API 엔드포인트
- Flutter: ResultScreen에 내보내기 버튼 추가 + 다운로드 + iOS 공유 시트 연동
- PDF 내용: 회의록 + 요약 + 액션 아이템을 하나의 문서로 결합
- 한국어 텍스트 지원: NotoSansKR 폰트

### 1.3 범위 외 (Out of Scope) - Phase 2

- DOCX 내보내기
- 이메일 발송
- 커스텀 PDF 템플릿/브랜딩
- Celery 기반 비동기 PDF 생성
- PDF 캐싱

---

## 2. 요구사항 (Requirements) - EARS 형식

### REQ-EXPORT-001: PDF 생성 엔드포인트

**WHEN** 사용자가 GET `/api/v1/export/pdf/{minutes_task_id}`를 요청하면
**THEN** 시스템은 해당 task_id의 회의록 데이터를 조회하여 PDF를 생성하고, `application/pdf` Content-Type의 StreamingResponse로 반환해야 한다.

- 응답 헤더: `Content-Disposition: attachment; filename="minutes_{task_id}.pdf"`
- PDF 생성은 동기 처리 (fpdf2 사용)

### REQ-EXPORT-002: PDF 콘텐츠 구조

시스템은 **항상** 다음 섹션을 순서대로 포함하는 PDF를 생성해야 한다:

1. **헤더**: 회의 제목, 생성 날짜/시간, 총 발화 시간
2. **발화자 통계**: 발화자별 발화 횟수 및 총 발화 시간 테이블
3. **회의록 본문**: 발화자별 타임스탬프와 발화 내용 (speaker_name, start~end, text)
4. **요약**: summary_text 전문
5. **주요 결정사항**: key_decisions[] 목록
6. **액션 아이템**: action_items[] 테이블 (담당자, 작업, 기한, 우선순위)

### REQ-EXPORT-003: 한국어 텍스트 렌더링

시스템은 **항상** NotoSansKR TTF 폰트를 fpdf2에 등록하여 한국어 텍스트를 정상적으로 렌더링해야 한다.

- NotoSansKR-Regular.ttf: 본문 텍스트
- NotoSansKR-Bold.ttf: 제목, 헤더, 강조 텍스트
- 폰트 파일 위치: `backend/assets/fonts/` 디렉토리

### REQ-EXPORT-004: Flutter 내보내기 기능

**WHEN** 사용자가 ResultScreen의 내보내기 버튼을 탭하면
**THEN** Flutter 앱은 Export API를 호출하여 PDF를 다운로드하고, iOS 공유 시트(share_plus)를 통해 공유할 수 있어야 한다.

- 내보내기 버튼: AppBar 우측에 아이콘 버튼으로 배치
- 다운로드: Dio를 사용하여 PDF 파일을 임시 디렉토리에 저장
- 공유: share_plus 패키지로 iOS Share Sheet 호출
- 로딩 상태: 다운로드 중 프로그레스 인디케이터 표시

### REQ-EXPORT-005: 오류 처리

**IF** 존재하지 않는 task_id로 PDF 내보내기를 요청하면
**THEN** 시스템은 HTTP 404 응답과 함께 `{"detail": "Minutes not found"}` 메시지를 반환해야 한다.

**IF** 회의록 데이터가 불완전한 경우 (segments가 비어있는 경우)
**THEN** 시스템은 HTTP 422 응답과 함께 `{"detail": "Incomplete minutes data"}` 메시지를 반환해야 한다.

**IF** Flutter에서 PDF 다운로드가 실패하면
**THEN** 앱은 사용자에게 SnackBar로 오류 메시지를 표시해야 한다.

---

## 3. 대상 파일 (Target Files)

| 파일 경로                                    | 작업   | 설명                                |
| -------------------------------------------- | ------ | ----------------------------------- |
| `backend/pipeline/pdf_generator.py`          | 신규   | fpdf2 기반 PDF 생성 로직            |
| `backend/app/api/v1/export.py`               | 신규   | Export API 라우터                   |
| `backend/schemas/export.py`                  | 신규   | Export 스키마                       |
| `backend/app/main.py`                        | 수정   | Export 라우터 등록                  |
| `pyproject.toml`                             | 수정   | fpdf2 의존성 추가                   |
| `deploy/requirements-ubuntu.txt`             | 수정   | fpdf2 의존성 추가                   |
| `client/lib/services/export_api.dart`        | 신규   | Export API 서비스                   |
| `client/lib/screens/result_screen.dart`      | 수정   | 내보내기 버튼 추가                  |
| `client/pubspec.yaml`                        | 수정   | share_plus 패키지 추가             |

---

## 4. 기술 제약사항 (Technical Constraints)

| 항목              | 제약                                                       |
| ----------------- | ---------------------------------------------------------- |
| PDF 라이브러리    | fpdf2 (경량, TTF 폰트 등록 지원)                           |
| 한국어 폰트       | NotoSansKR (Google Fonts, OFL 라이선스)                    |
| 데이터 소스       | Redis (24시간 TTL) - TTL 만료 시 SQLite fallback 필요      |
| 임시 파일         | PDF 생성 후 BytesIO로 메모리 내 처리 (파일 시스템 미사용)  |
| 동기 처리         | MVP 단계에서 Celery 미사용, 동기 PDF 생성                  |
| Flutter HTTP      | Dio 패키지 (프로젝트 기존 사용)                            |
| 공유 기능         | share_plus 패키지 (iOS Share Sheet)                        |

---

## 5. 추적성 태그 (Traceability)

- **SPEC**: SPEC-EXPORT-001
- **요구사항**: REQ-EXPORT-001 ~ REQ-EXPORT-005
- **수락 기준**: AC-EXPORT-001 ~ AC-EXPORT-005 (acceptance.md 참조)
- **관련 SPEC**: SPEC-MIN-001 (회의록 처리), SPEC-SUM-001 (요약 처리)
