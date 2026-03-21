---
id: SPEC-ERR-001
version: "1.0.0"
status: completed
created: 2026-03-21
updated: 2026-03-21
author: kisoo
priority: P2
issue_number: 0
---

# SPEC-ERR-001: 전역 예외 핸들러 및 에러 응답 표준화

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-21 | 초안 작성 | kisoo |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 런타임 | Python >= 3.11, FastAPI >= 0.135.1 |
| 기존 미들웨어 | auth, rate_limit, security_headers, request_id |

---

## 2. 가정 (Assumptions)

- 기존 엔드포인트의 HTTPException 사용 패턴은 유지하되, 전역 핸들러로 일관된 포맷을 보장한다.
- 프로덕션에서 스택 트레이스가 클라이언트에 노출되지 않아야 한다.
- 요청 ID(X-Request-ID)가 에러 응답에 포함되어 로그 추적이 가능해야 한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: 커스텀 예외 클래스

**[REQ-ERR-001] [유비쿼터스]** 시스템은 도메인별 예외 클래스 계층을 정의해야 한다 (VoiceNoteError → AudioProcessingError, StorageError, PipelineError).

**[REQ-ERR-002] [유비쿼터스]** 모든 커스텀 예외는 error_code(문자열), message(사용자 메시지), status_code(HTTP 상태 코드)를 포함해야 한다.

### 모듈 2: 전역 예외 핸들러

**[REQ-ERR-003] [이벤트 기반]** WHEN 처리되지 않은 예외가 발생 THEN 시스템은 일관된 JSON 에러 응답을 반환해야 한다.

**[REQ-ERR-004] [유비쿼터스]** 에러 응답 형식은 {"error_code": str, "message": str, "request_id": str} 이어야 한다.

**[REQ-ERR-005] [이벤트 기반]** WHEN 프로덕션 환경에서 500 에러 발생 THEN 스택 트레이스를 클라이언트에 노출하지 않고 로그에만 기록해야 한다.

**[REQ-ERR-006] [이벤트 기반]** WHEN RequestValidationError 발생 THEN 422 응답과 함께 구체적인 필드별 검증 실패 정보를 반환해야 한다.

### 모듈 3: 설정 검증 강화

**[REQ-ERR-007] [유비쿼터스]** Settings 클래스는 max_concurrent_jobs(1~10), max_file_size_mb(1~2000) 등 핵심 설정값의 범위를 검증해야 한다.

---

## 4. 인수 조건 (Acceptance Criteria)

### AC-1: 커스텀 예외 에러 응답
- **Given** 서버 실행 중
- **When** AudioProcessingError 발생 시
- **Then** {"error_code": "AUDIO_PROCESSING_ERROR", "message": "...", "request_id": "..."} 형식 응답

### AC-2: 미처리 예외 안전 처리
- **Given** 서버 실행 중
- **When** 예상치 못한 Exception 발생
- **Then** 500 응답 + 스택 트레이스 미노출 + 로그 기록

### AC-3: 검증 에러 상세 정보
- **Given** 파일 업로드 시
- **When** 잘못된 형식의 파일 전송
- **Then** 422 응답 + 필드별 상세 에러 정보

### AC-4: 설정 검증
- **Given** max_concurrent_jobs=0 설정 시
- **When** Settings 초기화
- **Then** ValidationError 발생

---

## 5. 기술 접근 방식

### 파일 구조

```
backend/
├── app/
│   ├── exceptions.py              # 커스텀 예외 클래스 계층
│   ├── error_handlers.py          # 전역 예외 핸들러
│   ├── config.py                  # 설정 검증 추가
│   └── main.py                    # 핸들러 등록
├── tests/unit/
│   ├── test_exceptions.py
│   ├── test_error_handlers.py
│   └── test_config_validation.py
```
