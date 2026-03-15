---
id: SPEC-STT-001
type: acceptance-criteria
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-STT-001: 인수 기준 (Acceptance Criteria)

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-15 | 초안 작성 | kisoo |

---

## 시나리오 1: 한국어 오디오 업로드 후 전사 결과 수신 (Happy Path)

**관련 요구사항**: REQ-STT-002, REQ-STT-005, REQ-STT-008, REQ-STT-010, REQ-STT-011

**Given** 30분 분량의 한국어 회의 녹음 WAV 파일이 준비되어 있을 때
**When** 클라이언트가 POST /api/v1/transcriptions에 해당 파일을 multipart/form-data로 업로드하면
**Then** 시스템은 201 응답과 함께 task_id, status_url, result_url을 반환하고
**And** 작업 상태가 pending -> processing -> completed 순서로 전이되며
**And** GET /api/v1/transcriptions/{task_id} 응답에 한국어 텍스트 세그먼트, 각 세그먼트의 start/end 타임스탬프, confidence 점수가 포함되어야 한다
**And** 응답 JSON의 language 필드가 "ko"이고, segments 배열의 각 항목에 id, start, end, text, confidence 필드가 존재해야 한다

---

## 시나리오 2: 잘못된 파일 형식 업로드 거부

**관련 요구사항**: REQ-STT-001, REQ-STT-003, REQ-STT-004

**Given** 지원하지 않는 형식의 파일(.exe, .pdf, .txt 등)이 준비되어 있을 때
**When** 클라이언트가 POST /api/v1/transcriptions에 해당 파일을 업로드하면
**Then** 시스템은 422 응답과 함께 "지원하지 않는 파일 형식" 관련 오류 메시지를 반환하고
**And** 오류 응답의 detail 배열에 field, message, type 필드가 포함되며
**And** 해당 파일이 서버 임시 저장소에 보관되지 않아야 한다

---

## 시나리오 3: 작업 상태 폴링을 통한 진행 추적

**관련 요구사항**: REQ-STT-010

**Given** 오디오 파일이 성공적으로 업로드되어 task_id를 받은 상태에서
**When** 클라이언트가 GET /api/v1/transcriptions/{task_id}/status를 주기적으로 요청하면
**Then** 첫 번째 응답에서 status가 "pending" 또는 "processing"이고
**And** 처리가 완료되면 status가 "completed"로 변경되며
**And** 응답에 task_id, status, created_at, updated_at 필드가 포함되어야 한다
**And** 실패 시 status가 "failed"로 변경되고 error_message가 포함되어야 한다

---

## 시나리오 4: Apple Silicon MLX 가속 사용 확인

**관련 요구사항**: REQ-STT-006, REQ-STT-020

**Given** M4 Mac Mini에서 STT 서비스가 실행 중일 때
**When** GET /api/v1/health/model을 요청하면
**Then** device 필드가 "mps"로 표시되어야 하고
**And** model_loaded 필드가 true여야 하며
**And** model_name 필드가 "whisper-large-v3-turbo"여야 하고
**And** memory_usage_mb 필드가 양수 값이어야 한다

---

## 시나리오 5: 대용량 파일 크기 제한

**관련 요구사항**: REQ-STT-001, REQ-STT-003, REQ-STT-004

**Given** 500MB를 초과하는 오디오 파일이 준비되어 있을 때
**When** 클라이언트가 POST /api/v1/transcriptions에 해당 파일을 업로드하면
**Then** 시스템은 422 응답과 함께 "파일 크기가 제한(500MB)을 초과합니다" 관련 오류를 반환해야 하고
**And** 해당 파일이 서버 저장소에 보관되지 않아야 한다

---

## 시나리오 6: 장시간 오디오 청크 분할 처리

**관련 요구사항**: REQ-STT-018, REQ-STT-008

**Given** 2시간 분량의 한국어 오디오 파일이 업로드되었을 때
**When** STT 워커가 해당 파일을 처리하면
**Then** 시스템은 오디오를 30분 단위 청크(4개)로 분할하고
**And** 각 청크의 전사 결과를 순차적으로 처리한 후
**And** 최종 결과에서 세그먼트의 타임스탬프가 원본 오디오 기준으로 정확하게 보정되어야 한다
**And** 청크 경계에서 5초 오버랩이 적용되어 발화 잘림이 최소화되어야 한다

---

## 시나리오 7: 손상된 오디오 파일 처리

**관련 요구사항**: REQ-STT-017, REQ-STT-009

**Given** 손상된(corrupt) 오디오 파일이 업로드되어 전사 작업이 시작되었을 때
**When** STT 워커가 오디오 전처리 단계에서 파일을 디코딩하려고 하면
**Then** 시스템은 작업 상태를 "failed"로 변경하고
**And** 구체적인 오류 메시지("파일 손상" 또는 "지원되지 않는 오디오 코덱")를 기록해야 하며
**And** 부분 결과가 최종 결과로 저장되지 않아야 한다
**And** GET /api/v1/transcriptions/{task_id}/status에서 failed 상태와 error_message를 확인할 수 있어야 한다

---

## 시나리오 8: 동시 처리 제한 초과 시 대기열 진입

**관련 요구사항**: REQ-STT-005, REQ-STT-010

**Given** 이미 3개의 STT 작업이 processing 상태로 실행 중일 때
**When** 클라이언트가 4번째 오디오 파일을 POST /api/v1/transcriptions에 업로드하면
**Then** 시스템은 201 응답과 함께 task_id를 반환하고
**And** 해당 작업의 상태는 "pending"으로 Celery 대기열에 추가되며
**And** 기존 3개 작업 중 하나가 완료되면 대기 중인 작업이 자동으로 processing 상태로 전이되어야 한다

---

## 시나리오 9: 서버 시작 후 모델 웜업 상태 확인

**관련 요구사항**: REQ-STT-021, REQ-STT-020

**Given** FastAPI 서버가 방금 시작되었을 때
**When** 서버의 lifespan 이벤트가 완료된 후 GET /api/v1/health/model을 요청하면
**Then** model_loaded 필드가 true여야 하고
**And** load_time_seconds 필드가 30초 이내의 양수 값이어야 하며
**And** device 필드가 "mps"(Apple Silicon 가속)로 표시되어야 한다
**And** 이후 첫 번째 전사 요청 시 모델 로딩 지연 없이 즉시 처리가 시작되어야 한다

---

## 시나리오 10: Redis 캐시를 통한 빠른 결과 조회

**관련 요구사항**: REQ-STT-012, REQ-STT-013

**Given** 전사 작업이 completed 상태이고 결과가 Redis에 캐시되어 있을 때
**When** 동일한 task_id로 GET /api/v1/transcriptions/{task_id}를 두 번째 조회하면
**Then** 시스템은 Redis 캐시에서 직접 결과를 반환해야 하고
**And** 응답 시간이 100ms 이내여야 하며
**And** 반환된 데이터가 첫 번째 조회 결과와 동일해야 한다

---

## 시나리오 11: 작업 삭제 시 관련 리소스 정리

**관련 요구사항**: REQ-STT-014

**Given** 전사 작업이 completed 상태이고 결과가 캐시와 저장소에 존재할 때
**When** 클라이언트가 DELETE /api/v1/transcriptions/{task_id}를 요청하면
**Then** 시스템은 해당 작업의 Redis 캐시를 삭제하고
**And** 결과 데이터 파일을 삭제하고
**And** 임시 오디오 파일을 삭제하며
**And** 이후 동일 task_id로 GET 요청 시 404 응답을 반환해야 한다

---

## 시나리오 12: 헬스체크 엔드포인트 정상 동작

**관련 요구사항**: REQ-STT-019

**Given** STT 서비스의 모든 구성 요소(FastAPI, Redis, Celery 워커)가 정상 실행 중일 때
**When** 클라이언트가 GET /api/v1/health를 요청하면
**Then** status 필드가 "healthy"여야 하고
**And** components.redis 필드가 "healthy"여야 하며
**And** components.celery_workers.status 필드가 "healthy"여야 하고
**And** components.ffmpeg 필드가 "available"이어야 한다

---

## 시나리오 13: 메모리 사용량 경고

**관련 요구사항**: REQ-STT-022

**Given** 시스템 메모리 사용량이 24GB의 80%(약 19GB)에 근접한 상태에서
**When** 메모리 모니터링 로직이 현재 사용량을 확인하면
**Then** 시스템은 WARNING 레벨의 로그를 기록해야 하고
**And** GET /api/v1/health/model 응답의 memory_usage_mb와 available_memory_mb 필드에 현재 상태가 반영되어야 한다

---

## Quality Gates

### TDD 커버리지

- 모든 API 엔드포인트(POST, GET, DELETE, health)에 대한 단위 테스트 작성
- 전체 테스트 커버리지 85% 이상 달성
- Pydantic 스키마 검증 테스트 포함
- 오디오 전처리 로직 단위 테스트 포함

### 통합 테스트

- 실제 mlx-whisper 모델을 사용한 짧은 오디오(1분 이내) 통합 테스트
- Celery 워커와 Redis를 포함한 전체 파이프라인 통합 테스트
- 파일 업로드부터 결과 조회까지 end-to-end 시나리오 검증

### 성능 검증

- 30분 한국어 오디오 처리 시간 측정: 2x 실시간(60분) 기준 이내
- 업로드 응답 시간 측정: 500ms 이내
- 상태 조회 응답 시간 측정: 100ms 이내
- 동시 3개 작업 처리 시 메모리 사용량이 19GB를 초과하지 않음

### Definition of Done

- [ ] 모든 EARS 요구사항(REQ-STT-001 ~ REQ-STT-022)에 대한 구현 완료
- [ ] 전체 테스트 커버리지 85% 이상
- [ ] 모든 인수 시나리오(1~13) 통과
- [ ] 성능 목표 달성 확인 (업로드 < 500ms, STT < 2x 실시간, 상태 조회 < 100ms)
- [ ] API 문서 자동 생성 (FastAPI Swagger/ReDoc)
- [ ] 구조화된 JSON 로깅 구현
- [ ] Docker Compose 환경에서 정상 동작 확인

---

*SPEC ID: SPEC-STT-001*
*생성일: 2026-03-15*
*상태: draft*
