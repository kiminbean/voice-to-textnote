# SPEC-APP-002 인수 조건

## AC-1: SSE 스트림 연결
- **Given** ProcessingScreen 진입
- **When** SSE 연결 성공
- **Then** 실시간 상태 업데이트 UI 반영

## AC-2: SSE 폴백
- **Given** SSE 연결 실패
- **When** 3초 타임아웃
- **Then** 폴링 자동 전환 + 토스트 알림

## AC-3: 에러 다이얼로그
- **Given** API 500 에러
- **When** 다이얼로그 표시
- **Then** "재시도" / "홈으로" 버튼 동작

## AC-4: 오프라인 배너
- **Given** 헬스체크 실패
- **When** 오프라인 감지
- **Then** 상단 배너 + 녹음 버튼 비활성화

## AC-5: Shimmer 로딩
- **Given** HomeScreen 로딩
- **When** 데이터 미수신
- **Then** shimmer 카드 3개 표시

## AC-6: 결과 실제 데이터
- **Given** ResultScreen (meeting_id)
- **When** API 성공
- **Then** 실제 회의록/요약/액션 아이템 표시

## AC-7: 결과 에러
- **Given** ResultScreen API 실패
- **When** 에러 발생
- **Then** 에러 위젯 + 재시도 버튼

## 엣지 케이스

- SSE 연결 중 앱 백그라운드 → 재연결 시도
- 대용량 회의록 (1시간) → 스크롤 성능 유지
- 동시 다수 작업 → 각각 독립 SSE 스트림
