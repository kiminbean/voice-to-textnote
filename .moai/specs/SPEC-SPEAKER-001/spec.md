---
id: SPEC-SPEAKER-001
version: "1.0.0"
status: completed
created: "2026-06-13"
updated: "2026-06-13"
author: MoAI
priority: medium
issue_number: 0
---

# SPEC-SPEAKER-001: 화자 프로필 관리 및 음성 분석

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-13 | 기존 구현 문서화 | MoAI |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 플랫폼 | M4 Mac Mini 24GB (Apple Silicon) |
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 데이터베이스 | PostgreSQL / SQLite (SQLAlchemy async) |
| 인증 | JWT |

---

## 2. 요구사항 (Requirements)

### 모듈 1: 화자 프로필 CRUD

**[REQ-SPEAKER-001] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/speakers 요청 THEN 시스템은 화자 프로필을 생성하고 201을 반환해야 한다.

**[REQ-SPEAKER-002] [유비쿼터스]** 시스템은 항상 사용자의 화자 프로필 목록을 반환해야 한다. task_id 지정 시 해당 회의록 + 전역 프로필을 포함한다. speaker_label 필터를 지원한다.

**[REQ-SPEAKER-003] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/speakers/{id} THEN 시스템은 프로필 단건을 반환해야 한다.

**[REQ-SPEAKER-004] [이벤트 기반]** WHEN 클라이언트가 PATCH /api/v1/speakers/{id} THEN 시스템은 이름/역할/메모를 수정해야 한다.

**[REQ-SPEAKER-005] [이벤트 기반]** WHEN 클라이언트가 DELETE /api/v1/speakers/{id} THEN 시스템은 프로필을 삭제하고 204를 반환해야 한다.

### 모듈 2: 음성 프로파일 분석

**[REQ-SPEAKER-006] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/speakers/{id}/analyze-samples로 오디오 파일을 업로드 THEN 시스템은 음성 샘플을 분석하고 프로필에 누적해야 한다.

**[REQ-SPEAKER-007] [이벤트 기반]** WHEN 클라이언트가 POST /api/v1/speakers/{id}/voice-profile로 사전 분석 결과를 전송 THEN 시스템은 음성 특성 프로파일을 생성/갱신해야 한다.

**[REQ-SPEAKER-008] [이벤트 기반]** WHEN 클라이언트가 GET /api/v1/speakers/{id}/voice-characteristics THEN 시스템은 누적된 음성 특성을 반환해야 한다.

---

## 3. 추적성 (Traceability)

| 요구사항 ID | 엔드포인트 |
|-------------|-----------|
| REQ-SPEAKER-001 | POST /api/v1/speakers |
| REQ-SPEAKER-002 | GET /api/v1/speakers |
| REQ-SPEAKER-003 | GET /api/v1/speakers/{id} |
| REQ-SPEAKER-004 | PATCH /api/v1/speakers/{id} |
| REQ-SPEAKER-005 | DELETE /api/v1/speakers/{id} |
| REQ-SPEAKER-006 | POST /api/v1/speakers/{id}/analyze-samples |
| REQ-SPEAKER-007 | POST /api/v1/speakers/{id}/voice-profile |
| REQ-SPEAKER-008 | GET /api/v1/speakers/{id}/voice-characteristics |

---

## 4. 구현 노트

- 구현 파일: `backend/app/api/v1/collaboration/speakers.py`
- 서비스: `backend/services/speaker_service.py`, `backend/services/speaker_voice_service.py`
- 스키마: `backend/schemas/speaker.py`
- 음성 분석은 SpeakerVoiceService가 담당 (오디오 업로드 → 분석 → 프로필 누적)
