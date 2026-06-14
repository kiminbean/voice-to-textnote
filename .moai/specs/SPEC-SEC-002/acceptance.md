# SPEC-SEC-002 Acceptance Criteria

## 자동화된 수락 기준

### AC-001: iOS ATS — Release 빌드 ATS 준수
**Given** iOS 앱이 Release 빌드로 컴파일됨
**When** Info.plist의 네트워크 보안 설정을 확인
**Then** `NSAllowsArbitraryLoads` 키가 존재하지 않아야 함
**And** `NSExceptionDomains`가 존재하지 않거나 프로덕션 도메인만 포함해야 함

### AC-002: iOS ATS — Debug 빌드 제한적 예외
**Given** iOS 앱이 Debug 빌드로 컴파일됨
**When** localhost 또는 100.110.255.105에 HTTP 요청
**Then** 연결이 허용되어야 함
**And** 그 외 도메인의 HTTP 연결은 차단되어야 함

### AC-003: Android Network Security — Release 빌드
**Given** Android 앱이 Release 빌드로 컴파일됨
**When** HTTP cleartext 요청 시도
**Then** 요청이 차단되어야 함

### AC-004: Android Network Security — Debug 빌드
**Given** Android 앱이 Debug 빌드로 컴파일됨
**When** localhost 또는 100.110.255.105에 HTTP 요청
**Then** 연결이 허용되어야 함

### AC-005: 매직 바이트 — 오디오 파일 시그니처 검증
**Given** 확장자가 `.wav`인 파일이 업로드됨
**When** 파일의 첫 16바이트가 `RIFF....WAVE` 시그니처와 일치하지 않음
**Then** 시스템이 HTTP 422 응답을 반환해야 함
**And** 파일이 저장되지 않아야 함

### AC-006: 매직 바이트 — 정상 파일 통과
**Given** 확장자가 `.m4a`인 정상 오디오 파일이 업로드됨
**When** 파일의 시그니처가 `ftypM4A`와 일치함
**Then** 파일이 정상적으로 처리되어야 함

### AC-007: 매직 바이트 — 템플릿 파일 검증
**Given** 확장자가 `.pdf`인 파일이 업로드됨
**When** 파일의 첫 4바이트가 `%PDF`가 아님
**Then** 시스템이 HTTP 422 응답을 반환해야 함

### AC-008: 매직 바이트 — octet-stream 우회 방지
**Given** content_type이 `application/octet-stream`이고 확장자가 `.wav`인 파일
**When** 파일 시그니처가 WAV가 아님
**Then** 시스템이 매직 바이트 검증을 수행하고 422를 반환해야 함

### AC-009: 보안 헤더 — HSTS (프로덕션)
**Given** 백엔드 환경이 production
**When** 클라이언트가 API 엔드포인트에 요청
**Then** 응답에 `Strict-Transport-Security: max-age=31536000; includeSubDomains` 헤더가 포함되어야 함

### AC-010: 보안 헤더 — HSTS (비프로덕션)
**Given** 백엔드 환경이 dev 또는 staging
**When** 클라이언트가 API 엔드포인트에 요청
**Then** 응답에 `Strict-Transport-Security` 헤더가 포함되지 않아야 함

### AC-011: 보안 헤더 — Referrer-Policy (항상)
**Given** 모든 환경
**When** 클라이언트가 API 엔드포인트에 요청
**Then** 응답에 `Referrer-Policy: strict-origin-when-cross-origin` 헤더가 포함되어야 함

### AC-012: 보안 헤더 — Permissions-Policy (항상)
**Given** 모든 환경
**When** 클라이언트가 API 엔드포인트에 요청
**Then** 응답에 `Permissions-Policy: camera=(), microphone=(), geolocation=()` 헤더가 포함되어야 함

### AC-013: 클라이언트 — 오디오 업로드 확장자 검증
**Given** 클라이언트에서 파일 선택
**When** 파일 확장자가 .wav, .mp3, .m4a, .ogg가 아님
**Then** 업로드가 차단되고 에러 메시지가 표시되어야 함

### AC-014: 클라이언트 — 오디오 업로드 크기 검증
**Given** 클라이언트에서 파일 선택
**When** 파일 크기가 500MB 초과
**Then** 업로드가 차단되고 에러 메시지가 표시되어야 함

### AC-015: 클라이언트 — 템플릿 업로드 크기 검증
**Given** 클라이언트에서 템플릿 파일 선택
**When** 파일 크기가 10MB 초과
**Then** 업로드가 차단되고 에러 메시지가 표시되어야 함

### AC-016: 클라이언트 — Release 로깅 게이트
**Given** 앱이 Release 빌드
**When** Dio 에러 인터셉터가 에러를 처리
**Then** `print()` 로깅이 실행되지 않아야 함

---

## 수동 수락 기준

### AC-M01: iOS 실기기 Release 빌드 HTTP 차단
**환경**: iOS 실기기 (iPhone), Release 빌드
**절차**:
1. Release 빌드 앱 실행
2. HTTP URL로 직접 요청 시도 (예: staging URL)
**기대 결과**: 연결 실패, ATS 차단

### AC-M02: Android 실기기 Debug 빌드 staging 연결
**환경**: Android 실기기, Debug 빌드, Tailscale 연결
**절차**:
1. Debug 빌드 앱 실행
2. staging URL(100.110.255.105)로 API 요청
**기대 결과**: 정상 연결 및 응답

### AC-M03: Android 실기기 Release 빌드 HTTP 차단
**환경**: Android 실기기, Release 빌드
**절차**:
1. Release 빌드 앱 실행
2. HTTP URL로 API 요청 시도
**기대 결과**: 연결 실패, cleartext 차단

---

## 품질 게이트

| 항목 | 기준 |
|------|------|
| 백엔드 테스트 | 기존 테스트 전체 통과 유지 + 신규 매직 바이트 테스트 통과 |
| Flutter 테스트 | 기존 테스트 전체 통과 유지 + 신규 파일 검증 테스트 통과 |
| dart analyze | error 0, warning 0 (신규 코드) |
| ruff check | error 0 |
| 코드 커버리지 | 신규 코드 85%+ |
