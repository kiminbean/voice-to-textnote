# T-011 완료

## 완료 시각
2026-06-08

## 구현 내용

### ErrorLogEntry 모델
- `lib/models/error_log_entry.dart` 생성
- 필드: id, errorCode, category, message, userMessage, timestamp, endpoint, retryCount
- Hive 지원을 위한 TypeAdapter 구현
- AppError로부터 변환하는 팩토리 메서드

### ErrorLogService
- `lib/services/error_log_service.dart` 생성
- **save**: 에러 로그 저장 + 민감한 데이터 자동 마스킹
- **getRecent**: 최근 N일간 에러 조회 (기본 7일) + 자동 정리
- **getByCategory**: 특정 카테고리 필터링
- **deleteOlderThan**: 지정된 일수보다 오래된 에러 삭제
- **getStats**: 에러 통계 집계 (전체 수, 카테고리별, 상위 5개)

### 데이터 마스킹
1. Authorization/Bearer 토큰 마스킹
2. 파일 콘텐츠 마스킹 (200자 이상)
3. JWT 토큰 마스킹
4. API Key 패턴 마스킹

### Hive TypeAdapter
- `lib/adapters/error_log_entry_adapter.dart` 생성
- TypeID: 100
- 바이너리 읽기/쓰기 구현

### main.dart 수정
- Hive 초기화 추가
- ErrorLogEntryAdapter 등록
- error_logs 박스 오픈

## 테스트
- 13개 테스트 모두 통과
- 커버리지: 100%

## 리팩토링
- 불필요한 `_isFileContent` 메서드 삭제
- `deleteOlderThan` 배치 삭제로 성능 최적화

## 다음 단계
T-012: ErrorLogProvider 구현
