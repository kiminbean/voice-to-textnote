---
id: SPEC-QA-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-QA-001: 회의 Q&A (자연어 질문)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 기존 구현 문서화 | MoAI |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 캐시 | Redis |
| AI | OpenAI 호환 API (settings.summary_model) |

---

## 2. 요구사항 (Requirements)

**[REQ-QA-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/qa/ask 요청 THEN 시스템은 회의 내용에 대한 자연어 질문에 답변을 반환해야 한다. thread_id를 통해 대화 맥락(이전 질문/답변)을 유지할 수 있다.

**[REQ-QA-002] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/qa/{task_id}/history 요청 THEN 시스템은 해당 회의록의 Q&A 이력을 반환해야 한다.

**[REQ-QA-003] [원치 않는 행동]** 시스템은 task_id가 존재하지 않으면 404 Not Found를 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-QA-001 | POST /api/v1/qa/ask |
| REQ-QA-002 | GET /api/v1/qa/{task_id}/history |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/audio/qa.py`
- 서비스: `backend/services/qa_service.py`
- 스키마: `backend/schemas/qa.py`
- 회의록 데이터는 Redis에서 조회, AI 답변은 OpenAI 호환 API 호출
