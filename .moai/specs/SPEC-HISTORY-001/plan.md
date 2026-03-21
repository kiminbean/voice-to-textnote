# SPEC-HISTORY-001 구현 계획

## Task 1: 스키마 (schemas/history.py)
- HistoryItem, HistoryListResponse (items, total, page, page_size)

## Task 2: API 엔드포인트 (app/api/v1/history.py)
- GET /history - 목록 (페이지네이션, 필터)
- GET /history/{task_id} - 상세
- DELETE /history/{task_id} - 삭제

## Task 3: main.py 라우터 등록
