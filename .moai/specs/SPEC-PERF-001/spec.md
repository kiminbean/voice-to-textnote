# SPEC-PERF-001: 장시간 녹음 안정성 개선

---
id: SPEC-PERF-001
title: Long Recording Stability Improvement
created: 2026-03-24
status: Implemented
priority: High (P1)
domain: PERF (Performance)
lifecycle: spec-anchored
related_specs:
  - SPEC-STT-001 (STT 파이프라인)
  - SPEC-DIA-001 (화자 분리)
  - SPEC-APP-001 (Flutter 앱)
  - SPEC-SSE-001 (실시간 진행률)
---

## 1. 환경 (Environment)

### 1.1 시스템 구성

- **백엔드**: FastAPI + Celery + Redis (브로커/결과 저장소)
- **STT 엔진**: openai-whisper (whisper-small), Ubuntu 서버, CPU 전용
- **화자 분리 엔진**: pyannote/speaker-diarization-3.1, CPU 전용
- **클라이언트**: Flutter iOS 앱 (Tailscale 경유 접속)
- **설정**: chunk_duration_minutes=30, max_file_size_mb=500, max_duration_hours=4

### 1.2 현재 파이프라인

```
오디오 업로드 -> STT (whisper, 30분 청크 분할) -> 화자 분리 (pyannote) -> 회의록 생성 -> 요약
```

### 1.3 현재 상태

- 클라이언트 측 타임아웃 이미 수정됨 (업로드 30초->10분, 폴링 5분->60분)
- STT는 chunk_manager.py를 통해 30분 단위 청크 분할 처리 중
- 화자 분리는 전체 오디오를 한 번에 처리 (청크 분할 없음)
- 30분 이상 녹음 시 화자 분리 단계에서 15-30분+ 처리 시간 발생
- Celery 작업 중복 실행 위험 (visibility_timeout 미설정)

## 2. 가정 (Assumptions)

### 2.1 기술적 가정

- pyannote 3.1은 부분 오디오에 대해서도 정상적으로 화자 분리를 수행할 수 있다
- 청크 단위 화자 분리 후 스피커 레이블 병합이 기술적으로 가능하다 (speaker embedding 유사도 기반)
- CPU 환경에서 30분 오디오의 화자 분리는 청크 분할 시 전체 처리보다 빠르거나 동등하다
- Redis visibility_timeout 값 변경은 기존 작업에 영향을 주지 않는다

### 2.2 비즈니스 가정

- 사용자는 최대 60분 길이의 녹음을 처리할 수 있어야 한다
- 처리 중 진행률 표시는 사용자 이탈 방지에 중요하다
- 부분 결과라도 전달하는 것이 전체 실패보다 낫다

### 2.3 검증 필요 가정

- pyannote 청크 분할 후 스피커 레이블 일관성 유지 여부 (실험 필요)
- 청크 경계에서 발화가 잘리는 경우의 처리 전략 (오버랩 구간 필요 가능성)

## 3. 요구사항 (Requirements)

### 3.1 핵심 요구사항 (HIGH)

#### REQ-PERF-001: 화자 분리 청크 분할 처리

**WHEN** 30분 이상의 오디오 파일이 화자 분리 단계에 도달하면, **THEN** 시스템은 오디오를 설정된 청크 단위(기본 10분)로 분할하여 각 청크별로 화자 분리를 수행하고, 결과를 병합해야 한다.

- 청크 간 오버랩 구간을 포함하여 발화 경계 손실을 방지해야 한다 (기본 30초 오버랩)
- 병합 시 speaker embedding 코사인 유사도 기반으로 동일 화자를 식별해야 한다
- STT의 chunk_manager.py 패턴을 참고하여 구현한다
- 위치: `backend/engines/diarization_engine.py`

#### REQ-PERF-002: Redis visibility_timeout 설정

시스템은 **항상** Celery Redis 브로커의 `visibility_timeout`을 7200초(2시간) 이상으로 설정해야 한다.

- `celery_app.py`의 `broker_transport_options`에 명시적으로 설정한다
- 장시간 작업의 중복 실행(re-delivery)을 방지하기 위함이다
- 위치: `backend/workers/celery_app.py`

### 3.2 중요 요구사항 (MEDIUM)

#### REQ-PERF-003: 화자 분리 중간 진행률 보고

**WHILE** 화자 분리 작업이 진행 중일 때, 시스템은 오디오 길이 기반 예상 진행률을 중간 업데이트해야 한다.

- 현재: 0.30 (시작) -> 0.80 (완료)로 즉시 점프
- 개선: 청크 처리 완료 시마다 진행률 업데이트 (예: 3개 청크면 0.30 -> 0.47 -> 0.63 -> 0.80)
- Redis 상태 업데이트 시 기존 불변 필드(created_at 등) 보존 필수
- 위치: `backend/workers/tasks/diarization_task.py`

#### REQ-PERF-004: SoftTimeLimitExceeded 예외 처리

**IF** Celery 작업에서 `SoftTimeLimitExceeded` 예외가 발생하면, **THEN** 시스템은 처리된 부분까지의 결과를 저장하고 사용자에게 부분 완료 상태를 보고해야 한다.

- 현재 `soft_time_limit=3600`이 설정되어 있으나 예외 핸들러가 없음
- 부분 결과 저장 후 상태를 `partial_complete`로 업데이트
- 사용자에게 "일부 구간만 처리되었습니다" 메시지 전달
- 위치: 모든 Celery task 파일

### 3.3 부가 요구사항 (LOW)

#### REQ-PERF-005: 예상 처리 시간 표시

**WHEN** 사용자가 녹음을 업로드하면, **THEN** Flutter 앱은 녹음 길이 기반 예상 처리 시간을 표시해야 한다.

- 예: "약 15분 소요 예상" (30분 녹음 기준)
- 예상 시간 계산 공식: `녹음_길이 * 처리_계수` (CPU 기준 약 0.5배)
- 현재 "처리 중..." 만 표시되는 문제 해결
- 위치: Flutter 클라이언트 코드

#### REQ-PERF-006: 서버 재시작 스크립트

시스템은 **항상** `deploy/restart.sh` 스크립트를 통해 원격 서버를 안전하게 재시작할 수 있어야 한다.

- `pkill -f uvicorn`으로 기존 프로세스 정리 후 새로 시작
- Celery 워커도 함께 재시작
- 위치: `deploy/restart.sh`

#### REQ-PERF-007: 실패 시 재시도 UX

**WHEN** 처리 단계에서 오류가 발생하면, **THEN** Flutter 앱은 사용자에게 해당 단계의 재시도 버튼을 제공해야 한다.

- 현재: 오류 메시지만 표시, 재시도 옵션 없음
- 개선: 실패한 단계별 재시도 API 호출 및 버튼 UI 제공
- 위치: Flutter 클라이언트 코드

## 4. 명세 (Specifications)

### 4.1 화자 분리 청크 분할 아키텍처

```
[전체 오디오]
    |
    v
[청크 분할기] -- chunk_duration=10분, overlap=30초
    |
    v
[청크 1] -> [화자 분리] -> [결과 1]
[청크 2] -> [화자 분리] -> [결과 2]  --> [스피커 병합기] -> [최종 결과]
[청크 3] -> [화자 분리] -> [결과 3]
    |
    v
[진행률 업데이트] (각 청크 완료 시)
```

### 4.2 스피커 병합 알고리즘

1. 각 청크에서 speaker embedding 추출
2. 인접 청크 간 오버랩 구간의 speaker embedding 코사인 유사도 계산
3. 유사도 임계값(기본 0.75) 이상이면 동일 화자로 매핑
4. 전체 청크에 걸쳐 글로벌 스피커 ID 할당
5. 오버랩 구간의 중복 세그먼트 제거

### 4.3 Celery 설정 변경 사항

```python
# celery_app.py 변경 내용
broker_transport_options = {
    'visibility_timeout': 7200,  # 2시간 (기본 3600초에서 변경)
}
```

### 4.4 SoftTimeLimitExceeded 처리 패턴

```python
# 각 Celery task에 적용할 패턴
from celery.exceptions import SoftTimeLimitExceeded

try:
    # 작업 수행
    result = process_audio(audio_path)
except SoftTimeLimitExceeded:
    # 부분 결과 저장
    save_partial_result(partial_data)
    update_status("partial_complete", "시간 초과로 일부만 처리됨")
```

### 4.5 진행률 업데이트 구조

| 단계 | 현재 진행률 | 개선 후 진행률 |
|------|------------|--------------|
| 화자 분리 시작 | 0.30 | 0.30 |
| 청크 1/3 완료 | - | 0.47 |
| 청크 2/3 완료 | - | 0.63 |
| 화자 분리 완료 | 0.80 | 0.80 |

### 4.6 예상 처리 시간 계산

| 녹음 길이 | STT 예상 | 화자 분리 예상 | 총 예상 시간 |
|----------|---------|-------------|------------|
| 10분 | ~2분 | ~3분 | ~7분 |
| 30분 | ~5분 | ~8분 | ~18분 |
| 60분 | ~10분 | ~15분 | ~35분 |

*CPU 전용 서버 기준, 실제 성능에 따라 계수 조정 필요*

## 5. 추적성 (Traceability)

| 요구사항 ID | 구현 위치 | 관련 이슈 | 우선순위 |
|------------|----------|----------|---------|
| REQ-PERF-001 | diarization_engine.py | 화자 분리 청크 분할 | HIGH |
| REQ-PERF-002 | celery_app.py | visibility_timeout 설정 | HIGH |
| REQ-PERF-003 | diarization_task.py | 중간 진행률 보고 | MEDIUM |
| REQ-PERF-004 | 모든 Celery task | SoftTimeLimitExceeded 처리 | MEDIUM |
| REQ-PERF-005 | Flutter 클라이언트 | 예상 처리 시간 표시 | LOW |
| REQ-PERF-006 | deploy/restart.sh | 서버 재시작 스크립트 | LOW |
| REQ-PERF-007 | Flutter 클라이언트 | 실패 시 재시도 UX | LOW |

## 6. 제약사항 (Constraints)

- 서버는 CPU 전용 (GPU 없음) - 모든 ML 처리가 CPU에서 수행됨
- pyannote 3.1은 진행률 콜백을 지원하지 않음 - 청크 단위 예측으로 우회
- Redis 상태 업데이트 시 기존 불변 필드(created_at 등) 보존 필수
- Flutter 클라이언트 변경은 iOS 빌드 및 배포 필요
