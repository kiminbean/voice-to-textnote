# SPEC-APP-002 구현 계획

## Phase 1: 기반 서비스 (SSE + 연결 상태)

### Task 1: SSE 서비스 (sse_service.dart)
- SSE 스트림 연결/해제
- 이벤트 파싱 (data: JSON)
- 재연결 로직 + 폴링 폴백

### Task 2: 연결 상태 서비스 (connectivity_service.dart)
- 30초 주기 헬스체크
- 연결 상태 스트림

### Task 3: 연결 상태 Provider (connectivity_provider.dart)
- isOnline 상태 관리

## Phase 2: 에러 UI 위젯

### Task 4: ErrorDialog (error_dialog.dart)
- Material 3 AlertDialog
- "재시도" / "홈으로" 버튼

### Task 5: OfflineBanner (offline_banner.dart)
- MaterialBanner
- "서버에 연결할 수 없습니다"

### Task 6: ErrorRetryWidget + EmptyStateWidget
- 데이터 로드 실패 / 빈 상태 표시

## Phase 3: 로딩 상태

### Task 7: ShimmerCard + ShimmerText
- shimmer 패키지 활용
- 리스트/텍스트 플레이스홀더

## Phase 4: 화면 수정

### Task 8: HomeScreen 수정
- shimmer 로딩 + 오프라인 배너

### Task 9: ProcessingScreen SSE 통합
- SSE 스트림 연결
- 폴백 로직
- 에러 UI

### Task 10: ResultScreen 실제 데이터 연동
- ResultProvider 추가
- API 데이터 로드
- 에러/빈 상태 처리

## Phase 5: Provider 수정

### Task 11: PipelineProvider SSE 통합
- 폴링 → SSE 전환
- 완료/실패 이벤트 처리

### Task 12: ResultProvider (신규)
- 회의록/요약/액션 아이템 로드

## 의존성

- shimmer: ^3.0.0
- connectivity_plus: ^6.0.0

## 리스크

- SSE가 웹 플랫폼에서 다르게 동작할 수 있음 → 폴링 폴백으로 해결
- shimmer 패키지 Flutter 3.24 호환성 → 테스트 필요
