# SPEC-PERSIST-001 인수 조건

## AC-1: 동기 세션
- get_sync_session → 동기 세션 반환

## AC-2: 결과 저장
- persist_task_result("test-1", "stt", "completed", {"text":"hello"}) → DB 저장

## AC-3: 실패 안전
- DB 연결 불가 시 persist_task_result → 예외 없이 로깅만

## AC-4: DB 폴백
- Redis 미스 + DB 존재 → 결과 반환 + Redis 복원
