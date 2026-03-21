# SPEC-DB-001 인수 조건

## AC-1: DB 연결
- **Given** DATABASE_URL=sqlite+aiosqlite:///test.db
- **When** async session 생성
- **Then** 정상 연결

## AC-2: SQLite 폴백
- **Given** DATABASE_URL 미설정
- **When** engine 초기화
- **Then** SQLite 파일 사용

## AC-3: 테이블 생성
- **Given** create_all 호출
- **When** DB 조회
- **Then** task_results, audit_logs 테이블 존재

## AC-4: 결과 저장
- **Given** task_id="test-1", task_type="stt", result={"text": "hello"}
- **When** save_result() 호출
- **Then** DB에 저장

## AC-5: 결과 조회
- **Given** AC-4 저장 후
- **When** get_result("test-1")
- **Then** 저장된 결과 반환

## AC-6: 결과 목록
- **Given** stt 3개, diarization 2개 저장
- **When** list_results(task_type="stt")
- **Then** 3개 반환
