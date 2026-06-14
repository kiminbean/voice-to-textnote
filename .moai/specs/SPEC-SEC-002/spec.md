---
id: SPEC-SEC-002
version: "1.0.0"
status: completed
created: "2026-06-14"
updated: "2026-06-14"
completed: "2026-06-14"
pr_number: 28
author: sisyphus
priority: high
issue_number: 27
depends_on: SPEC-SEC-001
---

# SPEC-SEC-002: 보안 강화 — ATS 프로덕션 설정 + 파일 매직 바이트 검증 + 보안 헤더 고도화

## HISTORY

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|----------|--------|
| 1.0.0 | 2026-06-14 | 초안 작성 — iOS ATS, Android Network Security, 매직 바이트 검증, 보안 헤더, 클라이언트 검증 | sisyphus |

---

## 1. 환경 (Environment)

| 항목 | 내용 |
|------|------|
| 백엔드 프레임워크 | FastAPI 0.135+ / Python 3.11+ |
| 클라이언트 프레임워크 | Flutter 3.24+ / Dart 3.5+ |
| iOS 네이티브 | Swift 5.9+, UIKit (Info.plist) |
| Android 네이티브 | Kotlin (AndroidManifest.xml, network_security_config.xml) |
| HTTP 클라이언트 | Dio ^5.4+ |
| 인증 | SPEC-SEC-001 기반 (API Key + JWT) |
| 테스트 | pytest (백엔드), flutter test (클라이언트) |
| 개발 방법론 | TDD (Red-Green-Refactor) |
| 선행 SPEC | SPEC-SEC-001 (completed) |

---

## 2. 가정 (Assumptions)

- SPEC-SEC-001의 모든 구현이 완료된 상태이다 (API Key 인증, 레이트 리미팅, CORS, 기본 보안 헤더).
- 현재 iOS Info.plist의 `NSAllowsArbitraryLoads=true`는 개발 편의를 위한 것이며, 프로덕션에서는 ATS를 준수해야 한다.
- Tailscale 네트워크 기반 staging 환경(`http://100.110.255.105:8000`)은 유지되며, 프로덕션은 HTTPS(`https://api.voicetextnote.com`)를 사용한다.
- 백엔드 파일 검증은 현재 확장자 + MIME 타입만 확인하며, 매직 바이트 검증은 없다.
- HSTS 헤더는 HTTPS 프로덕션 환경에서만 의미 있으므로, 환경 감지 후 조건부 적용한다.
- 기존 백엔드 테스트와 Flutter 테스트가 통과하는 상태를 유지해야 한다.

---

## 3. 요구사항 (Requirements)

### 모듈 1: iOS ATS Hardening

**[REQ-SEC-020] [상태 기반]** IF 앱이 Release 빌드로 컴파일되는 경우 THEN iOS Info.plist는 `NSAllowsArbitraryLoads` 키를 포함하지 않아야 한다 (ATS 완전 준수).

**[REQ-SEC-021] [상태 기반]** IF 앱이 Debug 빌드로 컴파일되는 경우 THEN iOS Info.plist는 `NSAllowsArbitraryLoads=true` 대신 `NSExceptionDomains`를 사용하여 localhost 및 Tailscale IP(100.110.255.105)에 대해서만 cleartext HTTP를 허용해야 한다.

**[REQ-SEC-022] [원치 않는 행동]** 프로덕션 Release 빌드는 어떠한 cleartext HTTP 트래픽도 허용하지 않아야 한다.

### 모듈 2: Android Network Security Config

**[REQ-SEC-030] [유비쿼터스]** 시스템은 Android 9+ (API 28+)에서 `network_security_config.xml`을 통해 네트워크 보안 정책을 적용해야 한다.

**[REQ-SEC-031] [상태 기반]** IF 앱이 Debug 빌드인 경우 THEN `network_security_config.xml`은 localhost 및 100.110.255.105에 대해서만 cleartext 트래픽을 허용해야 한다.

**[REQ-SEC-032] [상태 기반]** IF 앱이 Release 빌드인 경우 THEN `network_security_config.xml`은 모든 cleartext 트래픽을 차단해야 한다.

### 모듈 3: 파일 매직 바이트 검증 (백엔드)

**[REQ-SEC-040] [이벤트 기반]** WHEN 클라이언트가 오디오 파일을 업로드하는 경우 THEN 시스템은 파일의 첫 N 바이트를 검사하여 실제 파일 시그니처(WAV: `RIFF....WAVE`, MP3: `ID3`/`FF FB`, M4A: `ftypM4A`, OGG: `OggS`)가 확장자와 일치하는지 확인해야 한다.

**[REQ-SEC-041] [이벤트 기반]** WHEN 클라이언트가 템플릿 파일을 업로드하는 경우 THEN 시스템은 파일 시그니처(PDF: `%PDF`, DOCX: `PK..504B`)를 검증해야 한다.

**[REQ-SEC-042] [이벤트 기반]** WHEN 파일 시그니처가 확장자와 불일치하는 경우 THEN 시스템은 HTTP 422 응답을 반환하고 파일을 저장하지 않아야 한다.

**[REQ-SEC-043] [원치 않는 행동]** 시스템은 `application/octet-stream` MIME 타입의 파일에 대해서도 매직 바이트 검증을 우회하지 않아야 한다.

### 모듈 4: 보안 헤더 고도화

**[REQ-SEC-050] [상태 기반]** IF 백엔드 환경이 production인 경우 THEN 시스템은 모든 응답에 `Strict-Transport-Security: max-age=31536000; includeSubDomains` 헤더를 추가해야 한다.

**[REQ-SEC-051] [유비쿼터스]** 시스템은 모든 응답에 `Referrer-Policy: strict-origin-when-cross-origin` 헤더를 추가해야 한다.

**[REQ-SEC-052] [유비쿼터스]** 시스템은 모든 응답에 `Permissions-Policy: camera=(), microphone=(), geolocation=()` 헤더를 추가해야 한다.

### 모듈 5: 클라이언트 파일 검증

**[REQ-SEC-060] [이벤트 기반]** WHEN 클라이언트가 오디오 파일을 업로드하기 전 THEN 시스템은 파일 확장자가 허용 목록(.wav, .mp3, .m4a, .ogg)에 포함되어 있는지 확인하고, 불일치 시 업로드를 차단해야 한다.

**[REQ-SEC-061] [이벤트 기반]** WHEN 클라이언트가 오디오 파일을 업로드하기 전 THEN 시스템은 파일 크기가 500MB를 초과하는지 확인하고, 초과 시 업로드를 차단하고 사용자에게 알려야 한다.

**[REQ-SEC-062] [이벤트 기반]** WHEN 클라이언트가 템플릿 파일을 업로드하기 전 THEN 시스템은 파일 크기가 10MB를 초과하는지 확인하고, 초과 시 업로드를 차단해야 한다.

**[REQ-SEC-063] [상태 기반]** IF 앱이 Release 빌드인 경우 THEN Dio 에러 인터셉터의 `print()` 로깅이 비활성화되어야 한다 (`kDebugMode` 게이트).

---

## 4. 제약사항 (Constraints)

| 제약 | 설명 |
|------|------|
| iOS Info.plist 분리 | Flutter는 기본적으로 단일 Info.plist 사용. 환경 분리는 xcconfig 전처리 또는 빌드 스크립트 필요 |
| Android min SDK | API 29 (Android 10). cleartext 차단이 기본 동작 |
| 매직 바이트 의존성 | `python-magic`은 libmagic 시스템 의존성 필요. 대안: 순수 Python 시그니처 매칭 (권장) |
| HSTS 조건부 적용 | HTTP 환경(dev/staging)에서 HSTS 헤더는 브라우저가 무시함. 프로덕션 환경 감지 후 적용 |
| 기존 테스트 호환성 | 기존 `application/octet-stream` 허용 로직과 매직 바이트 검증의 충돌 해결 필요 |

---

## 5. 위험 및 완화 (Risks & Mitigation)

| 위험 | 확률 | 영향 | 완화 전략 |
|------|------|------|-----------|
| iOS Info.plist 환경 분리 빌드 실패 | 중 | 높음 | xcconfig 기반 접근, Flutter build flavor 사용 |
| 매직 바이트 검증이 정상 파일을 거부 | 낮음 | 중 | 시그니처 매칭에 유연성 확보 (변형 허용), 전체 오디오 파일 테스트 |
| Android cleartext 차단으로 staging 연결 불가 | 중 | 중 | Debug 빌드에만 cleartext 예외 적용 |
| HSTS가 HTTP 환경에서 경고 | 낮음 | 낮음 | 프로덕션 환경 감지 후 조건부 헤더 |

---

## 6. 수락 기준 (Acceptance Criteria)

자동화된 수락 기준은 `acceptance.md`를 참조.

### 자동화 기준
- AC-001: Release 빌드 Info.plist에 NSAllowsArbitraryLoads 없음
- AC-002: network_security_config.xml이 Debug/Release 분리됨
- AC-003: 매직 바이트 불일치 시 422 반환
- AC-004: 프로덕션 환경에서 HSTS 헤더 존재
- AC-005: 클라이언트 오디오 업로드 전 크기/확장자 검증
- AC-006: AndroidManifest가 `network_security_config`를 참조하고 cleartext 예외가 localhost/staging으로 제한됨

### 수동 기준
- AC-M01: iOS 실기기 Release 빌드에서 HTTP 차단 확인
- AC-M02: Android 실기기 Debug 빌드에서 staging 연결 확인
- AC-M03: Android 실기기 Release 빌드에서 HTTP 차단 확인

### 2026-06-14 재검증

- `client/test/config/network_security_config_test.dart` 추가: AndroidManifest 참조, base cleartext 차단, localhost/Tailscale staging 예외만 허용하는 정적 회귀 테스트.
- `cd client && flutter test test/config/network_security_config_test.dart` -> `3 passed`
- `cd client && flutter test` -> `324 passed`
- `cd client && flutter analyze` -> `No issues found!`
- Android 에뮬레이터/실기기에서 실제 네트워크 차단/허용을 관측하는 AC-M02/AC-M03은 장비 기반 수동 검증으로 유지한다.

---

## 7. Implementation Notes (As-Implemented)

구현 완료일: 2026-06-14 / PR: #28

### 모듈 1: iOS ATS Hardening (REQ-SEC-020~022)
- Info.plist: `NSAllowsArbitraryLoads=false` 설정, `NSExceptionDomains`로 localhost + 100.110.255.105만 cleartext HTTP 예외
- 단일 Info.plist + 환경 변수 기반 접근 (xcconfig 분리 대신 동적 예외 도메인 사용)

### 모듈 2: Android Network Security (REQ-SEC-030~032)
- `network_security_config.xml` 신규 생성: `base-config cleartextTrafficPermitted="false"`
- localhost + 100.110.255.105만 `domain-config` 예외
- AndroidManifest.xml에 `networkSecurityConfig` 참조 추가

### 모듈 3: 매직 바이트 검증 (REQ-SEC-040~043)
- `file_signature.py` 신규: 순수 Python 시그니처 매칭 (python-magic 외부 의존성 없음)
- `validators.py`: `validate_audio_format`에 `file_header` 파라미터 추가 (하위 호환)
- transcription.py: 디스크 저장 후 헤더 16바이트 읽어 검증, unlink 순서 개선 (개별 삭제 → 일괄 삭제)
- batch.py: `raw_content[:16]`으로 검증
- templates.py: `_validate_file`에 `file_header` 전달, `verify_file_signature` import

### 모듈 4: 보안 헤더 (REQ-SEC-050~052)
- `security_headers.py`: HSTS(production만, `max-age=31536000; includeSubDomains`), Referrer-Policy, Permissions-Policy, CSP 추가
- HSTS는 `settings.environment == "production"`일 때만 적용

### 모듈 5: 클라이언트 검증 (REQ-SEC-060~063)
- `file_validator.dart` 신규: 매직 바이트 + 확장자 + 500MB 크기 검증
- `transcription_api.dart`: `upload()` 전 `validateAudioFile()` 호출

### 테스트 결과
- Backend: 3246 passed, 2 pre-existing env failures (MLX/Celery 환경 의존, 본 SPEC 무관)
- Flutter: 301 passed
- 신규 테스트: test_file_signature.py (22 tests), test_security_headers.py (HSTS/Referrer/Permissions/CSP)
- 기존 테스트 수정: test_batch_api (side_effect 3개), test_transcription_api (invalid_signature), test_templates_api (DOCX 매직 바이트), transcription_api_test.dart (M4A 매직 바이트)
