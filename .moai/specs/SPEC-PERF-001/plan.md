# SPEC-PERF-001: 구현 계획

## 구현 전략

DDD 방식 (ANALYZE-PRESERVE-IMPROVE) — 기존 코드 수정이 많으므로 동작 보존 우선

## Phase 분해

### Phase 1: HIGH 우선순위 (핵심 안정성)

#### Task 1.1: Redis visibility_timeout 설정 (REQ-PERF-002)
- **파일**: `backend/workers/celery_app.py`
- **작업**: `broker_transport_options`에 `visibility_timeout: 7200` 추가
- **예상 시간**: 5분
- **위험도**: 낮음 (설정 변경만)

#### Task 1.2: 화자 분리 청크 분할 구현 (REQ-PERF-001)
- **파일**: `backend/ml/diarization_engine.py`, `backend/pipeline/dia_chunk_manager.py` (신규)
- **작업**:
  1. `dia_chunk_manager.py` 생성 — 오디오 청크 분할 (10분 단위, 30초 오버랩)
  2. `diarization_engine.py`에 `diarize_chunked()` 메서드 추가
  3. 청크별 화자 세그먼트 병합 로직 (오버랩 구간 기반 스피커 매핑)
  4. `diarization_task.py`에서 30분 이상일 때 청크 분할 호출
- **예상 시간**: 2-3시간
- **위험도**: 높음 (청크 간 스피커 ID 일관성 검증 필요)
- **참고 구현**: `backend/pipeline/chunk_manager.py` (STT 청크 분할 패턴)

### Phase 2: MEDIUM 우선순위 (사용자 경험)

#### Task 2.1: 화자 분리 중간 진행률 보고 (REQ-PERF-003)
- **파일**: `backend/workers/tasks/diarization_task.py`
- **작업**: 청크 처리 완료 시마다 `_update_task_status()` 호출
- **예상 시간**: 30분
- **의존성**: Task 1.2 완료 후

#### Task 2.2: SoftTimeLimitExceeded 예외 처리 (REQ-PERF-004)
- **파일**: `backend/workers/tasks/transcription_task.py`, `diarization_task.py`
- **작업**:
  1. `celery.exceptions.SoftTimeLimitExceeded` import
  2. 메인 try 블록에 except 핸들러 추가
  3. 부분 결과 저장 및 `partial_complete` 상태 업데이트
- **예상 시간**: 1시간
- **위험도**: 낮음

### Phase 3: LOW 우선순위 (부가 기능)

#### Task 3.1: 서버 재시작 스크립트 (REQ-PERF-006)
- **파일**: `deploy/restart.sh` (신규)
- **작업**: uvicorn + celery 재시작 스크립트 작성
- **예상 시간**: 15분

#### Task 3.2: 예상 처리 시간 표시 (REQ-PERF-005)
- **파일**: `client/lib/providers/pipeline_provider.dart`, `client/lib/widgets/pipeline_progress.dart`
- **작업**: 녹음 길이 기반 예상 시간 계산 및 UI 표시
- **예상 시간**: 1시간

#### Task 3.3: 실패 시 재시도 UX (REQ-PERF-007)
- **파일**: `client/lib/screens/processing_screen.dart`, `client/lib/providers/pipeline_provider.dart`
- **작업**: 실패 단계 재시도 버튼 추가
- **예상 시간**: 1시간

## 기술 의존성

```
Task 1.1 (visibility_timeout) ─── 독립 실행 가능
Task 1.2 (청크 분할) ─── 독립 실행 가능
  └── Task 2.1 (진행률) ─── Task 1.2 완료 후
Task 2.2 (타임아웃 처리) ─── 독립 실행 가능
Task 3.1 (재시작 스크립트) ─── 독립 실행 가능
Task 3.2 (예상 시간) ─── 독립 실행 가능
Task 3.3 (재시도 UX) ─── 독립 실행 가능
```

## 리스크 분석

| 리스크 | 확률 | 영향 | 완화 전략 |
|--------|------|------|----------|
| 청크 간 스피커 ID 불일치 | 중간 | 높음 | 오버랩 구간 30초로 충분한 매칭 컨텍스트 확보 |
| pyannote embedding 추출 API 제한 | 낮음 | 높음 | 오버랩 구간의 타임스탬프 기반 매핑으로 우회 |
| 청크 분할 시 메모리 증가 | 낮음 | 중간 | 청크별 순차 처리로 메모리 피크 제어 |
| SoftTimeLimitExceeded 발생 시 데이터 손실 | 중간 | 중간 | 청크 단위 중간 결과 저장 |

## 테스트 전략

- **단위 테스트**: 청크 분할/병합 로직, 스피커 매핑 알고리즘
- **통합 테스트**: 30분+ 오디오 모의 처리 파이프라인
- **수동 테스트**: 실제 30분 녹음으로 전체 파이프라인 E2E 검증
