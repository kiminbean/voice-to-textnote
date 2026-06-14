# SPEC-SEC-002 Implementation Plan

## 개요

- **SPEC ID**: SPEC-SEC-002
- **개발 방법론**: TDD (Red-Green-Refactor)
- **브랜치**: feature/SPEC-SEC-002
- **선제 조건**: SPEC-SEC-001 (completed)

---

## 기술 스택

| 항목 | 기술 | 버전 |
|------|------|------|
| 백엔드 | FastAPI + Python | 0.135+ / 3.11+ |
| 클라이언트 | Flutter + Dart | 3.24+ / 3.5+ |
| iOS | Info.plist + xcconfig | iOS 15+ |
| Android | network_security_config.xml | API 29+ |
| 파일 검증 | 순수 Python 매직 바이트 매칭 | (외부 의존성 없음) |

---

## 작업 분해 (5배치)

### Batch 1: 백엔드 매직 바이트 검증 (REQ-SEC-040~043)
**난이도**: High | **예상 변경 파일**: 3

1. `backend/utils/file_signature.py` (신규) — 파일 시그니처 매칭 유틸리티
   - WAV: `RIFF` (offset 0) + `WAVE` (offset 8)
   - MP3: `ID3` (offset 0) 또는 `FF FB` / `FF F3` / `FF F2` (offset 0)
   - M4A: `ftyp` (offset 4) + `M4A` (offset 8)
   - OGG: `OggS` (offset 0)
   - PDF: `%PDF` (offset 0)
   - DOCX: `PK\x03\x04` (offset 0, ZIP 시그니처)

2. `backend/utils/validators.py` (수정) — `validate_audio_format`에 매직 바이트 검증 통합
   - 확장자 → 예상 시그니처 매핑
   - 첫 16바이트 읽어 시그니처 검증
   - UploadFile.seek(0) 복원 필수

3. `backend/app/api/v1/admin/templates.py` (수정) — `_validate_file`에 매직 바이트 검증 추가

**테스트**:
- `backend/tests/unit/test_file_signature.py` (신규) — 각 시그니처별 매칭 테스트
- `backend/tests/unit/test_validators.py` (확장) — 매직 바이트 검증 통합 테스트
- 변조된 확장자 파일 거부 테스트 (.txt → .wav 변경 시 거부)

### Batch 2: 보안 헤더 고도화 (REQ-SEC-050~052)
**난이도**: Low | **예상 변경 파일**: 1

1. `backend/app/middleware/security_headers.py` (수정)
   - HSTS: `Strict-Transport-Security: max-age=31536000; includeSubDomains` (프로덕션만)
   - `Referrer-Policy: strict-origin-when-cross-origin` (항상)
   - `Permissions-Policy: camera=(), microphone=(), geolocation=()` (항상)
   - 프로덕션 감지: `settings.environment == "production"`

**테스트**:
- `backend/tests/unit/test_security_headers.py` (확장) — 헤더 존재 확인, 프로덕션/비프로덕션 조건부 확인

### Batch 3: iOS ATS Hardening (REQ-SEC-020~022)
**난이도**: High | **예상 변경 파일**: 3

1. `client/ios/Runner/Info.plist` (수정)
   - `NSAllowsArbitraryLoads` 제거
   - `NSExceptionDomains` 추가 (localhost, 100.110.255.105)
   - Release 빌드에서는 ATS 완전 준수

2. `client/ios/Flutter/Debug.xcconfig` (수정/확인)
   - Debug 빌드에서 cleartext 예외 허용 위한 xcconfig 설정

3. `client/ios/Flutter/Release.xcconfig` (수정/확인)
   - Release 빌드에서 ATS 완전 준수 확인

**접근법**:
- Flutter의 단일 Info.plist 제약 → `NSExceptionDomains` 기반 도메인별 예외로 해결
- Debug: `NSAllowsArbitraryLoads=true` + `NSExceptionDomains` (가장 관대하지만 개발용)
- Release: `NSAllowsArbitraryLoads` 제거, `NSExceptionDomains` 없음 (ATS 완전 준수)
- 빌드 분리: Flutter `--dart-define` 외부에서 처리 불가 → Info.plist를 빌드 전 처리 스크립트 또는 Xcode Build Phase로 환경별 치환

### Batch 4: Android Network Security Config (REQ-SEC-030~032)
**난이도**: Medium | **예상 변경 파일**: 3

1. `client/android/app/src/main/res/xml/network_security_config.xml` (신규)
   - Release/Profile baseline: HTTPS만 허용
   - cleartext domain 예외 없음

2. `client/android/app/src/main/AndroidManifest.xml` (수정)
   - `<application>` 태그에 `android:networkSecurityConfig="@xml/network_security_config"` 추가

3. `client/android/app/src/debug/res/xml/network_security_config.xml` (신규)
   - Debug 빌드용 localhost + 100.110.255.105 cleartext 예외 오버레이 확인

**테스트**:
- 클라이언트 통합 테스트 (HTTP 차단/허용 시나리오)
- 안드로이드 에뮬레이터 기반 수동 검증 (AC-M02, AC-M03)

### Batch 5: 클라이언트 파일 검증 + 로깅 (REQ-SEC-060~063)
**난이도**: Medium | **예상 변경 파일**: 3

1. `client/lib/utils/file_validator.dart` (신규) — 파일 검증 유틸리티
   - 확장자 화이트리스트 확인
   - 파일 크기 확인 (500MB 오디오, 10MB 템플릿)
   - 업로드 전 사전 검증 인터페이스

2. `client/lib/services/transcription_api.dart` (수정) — 업로드 전 파일 검증 호출
3. `client/lib/screens/template_screen.dart` (수정) — 크기 검증 추가
4. `client/lib/services/api_client.dart` (수정) — `print()` → `kDebugMode` 게이트

**테스트**:
- `client/test/utils/file_validator_test.dart` (신규) — 확장자/크기 검증 단위 테스트
- 기존 `transcription_api_test.dart` 확장 — 검증 실패 시나리오

---

## 병렬 실행 기회

| 병렬 그룹 | 배치 | 이유 |
|-----------|-------|------|
| A | Batch 1 (백엔드 매직 바이트) + Batch 2 (보안 헤더) | 독립적인 백엔드 변경 |
| B | Batch 3 (iOS) + Batch 4 (Android) | 독립적인 플랫폼 설정 |
| C | Batch 5 (클라이언트 검증) | 프론트엔드 독립 |

권장 순서: A (병렬) → B (병렬) → C

---

## 의존성 분석

```
Batch 1 (매직 바이트) ──┐
                         ├──→ Batch 5 (클라이언트 검증)
Batch 2 (보안 헤더) ─────┘        ↑
                                   │ (백엔드 검증과 클라이언트 검증은 독립)
Batch 3 (iOS ATS) ─── 독립 ──────┘
Batch 4 (Android) ─── 독립 ──────┘
```

---

## MX 태그 계획

| 타겟 | 태그 | 이유 |
|------|------|------|
| `validators.py:validate_audio_format` | @MX:ANCHOR | fan_in >= 3 (transcription, batch, speakers) |
| `security_headers.py` | @MX:NOTE | 보안 헤더 정책 SSOT |
| `file_signature.py` (신규) | @MX:NOTE | 파일 시그니처 매핑 규칙 |
