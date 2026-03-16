# SPEC-OPS-001 구현 계획

## 구현 순서

### Task 1: Prometheus 메트릭 설정
- prometheus-fastapi-instrumentator 설치
- backend/app/metrics.py 생성
- 커스텀 메트릭 정의 (활성 작업 수, 처리 시간, 실패 수)
- main.py에 instrumentator 등록

### Task 2: 요청 ID 미들웨어
- backend/app/middleware/request_id.py 생성
- UUID 기반 요청 ID 생성/전파
- structlog 컨텍스트에 request_id 바인딩

### Task 3: Readiness 엔드포인트
- /api/v1/health/ready 추가
- Redis ping, Celery inspect 확인

### Task 4: 커스텀 메트릭 계측
- Celery 태스크에 메트릭 카운터/히스토그램 추가
- 메모리/CPU 메트릭 노출

## 의존성

- prometheus-fastapi-instrumentator
- prometheus-client (자동 설치됨)

## 리스크

- prometheus-fastapi-instrumentator와 FastAPI 버전 호환성
- Celery inspect가 워커 미실행 시 타임아웃 → 타임아웃 설정 추가
