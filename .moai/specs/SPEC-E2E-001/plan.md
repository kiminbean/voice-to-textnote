---
spec_id: SPEC-E2E-001
type: plan
version: "1.0.0"
created: 2026-03-15
updated: 2026-03-15
author: kisoo
---

# SPEC-E2E-001 구현 계획: E2E 통합 테스트

---

## 1. 구현 개요

### 신규 파일

```
backend/
  tests/
    e2e/
      __init__.py
      conftest.py              # E2E 전용 픽스처 (Redis mock, Celery mock, 데이터)
      test_pipeline_e2e.py     # 전체 파이프라인 E2E 테스트
```

### 구현 순서

| TASK | 내용 |
|------|------|
| TASK-001 | E2E conftest.py: Redis in-memory mock, Celery task mock, 단계별 결과 데이터 |
| TASK-002 | 단계별 연결 테스트: STT→DIA, DIA→MIN, MIN→SUM |
| TASK-003 | 전체 파이프라인 테스트: STT→DIA→MIN→SUM 순차 검증 |
| TASK-004 | 에러 전파 + 동시 제한 테스트 |

---

## 2. 핵심 설계

### Redis In-Memory Mock

```python
class InMemoryRedis:
    """키-값 저장/조회/삭제 + Set 연산을 시뮬레이션"""
    storage: dict[str, str]
    sets: dict[str, set]

    async def get(key) -> str | None
    async def setex(key, ttl, value) -> bool
    async def delete(*keys) -> int
    async def scard(key) -> int
    async def sadd(key, *members) -> int
    async def srem(key, *members) -> int
    async def set(key, value) -> bool
    async def incr(key) -> int
    async def decr(key) -> int
    async def ping() -> bool
```

### 테스트 전략

- 각 테스트는 E2E conftest의 `e2e_client` 픽스처 사용
- Redis in-memory mock이 실제 저장/조회 동작 수행
- Celery delay()는 mock이지만, 테스트에서 직접 Redis에 결과 주입
- 파이프라인 흐름: API 호출 → Redis에 결과 주입 → 다음 단계 API 호출

---

*Plan ID: SPEC-E2E-001*
*생성일: 2026-03-15*
*상태: completed*
