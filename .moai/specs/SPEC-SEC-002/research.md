# SPEC-SEC-002 Research: 보안 강화 — ATS + 파일 검증 + 보안 헤더

## 연구 일자
- 2026-06-14

## 연구 범위
- iOS ATS (App Transport Security) 설정
- Android Network Security Config
- 파일 업로드 매직 바이트 검증 (프론트엔드 + 백엔드)
- 보안 헤더 고도화 (HSTS, Referrer-Policy, Permissions-Policy)
- 인증서 피닝 (Certificate Pinning) — 향후 고려사항으로 기록

---

## 1. iOS ATS 현황 (CRITICAL)

### 파일: `client/ios/Runner/Info.plist` (lines 29-33)

```xml
<key>NSAppTransportSecurity</key>
<dict>
    <key>NSAllowsArbitraryLoads</key>
    <true/>
</dict>
```

### 발견사항
- **ATS 전역 비활성화** — 가장 관대한 설정. 모든 HTTP cleartext 트래픽 허용
- **NSExceptionDomains 없음** — 도메인별 예외 없이 전체 비활성화
- **Debug/Release 분리 없음** — Info.plist가 하나만 존재. Release 빌드에도 동일한 설정 적용
- **App Store 리젝 위험** — 프로덕션 빌드에서 정당한 사유 없이 NSAllowsArbitraryLoads=true 사용 시 리뷰 거절 가능성

### 권장 해결책
- Debug: `NSAllowsArbitraryLoads=true` 유지 (개발 편의성)
- Release: ATS 완전 준수 (NSAllowsArbitraryLoads 제거)
- Flutter에서는 Info.plist 환경 분리를 위해 Xcode Build Configuration 별 파일 사용 또한 `xcconfig` 기반 전처리 필요
- 대안: Tailscale IP를 NSExceptionDomains에 등록 (staging 환경용)

---

## 2. Android Network Security 현황

### 파일: `client/android/app/src/main/AndroidManifest.xml` (lines 16-20)

### 발견사항
- **`android:usesCleartextTraffic` 미설정** — 기본값(false) 적용. Android 9+에서 HTTP 트래픽 차단
- **`android:networkSecurityConfig` 미설정** — 네트워크 보안 정책 파일 없음
- **`network_security_config.xml` 존재하지 않음** — glob 검색 결과 없음
- **크로스 플랫폼 불일치**: iOS는 HTTP 허용, Android는 HTTP 차단 → staging 환경(http://100.110.255.105:8000)에서 Android 작동 불가

### 권장 해결책
- `network_security_config.xml` 생성
- Debug/Staging: Tailscale IP (100.110.255.105) + localhost에 cleartext 예외
- Release: HTTPS만 허용, cleartext 완전 차단
- AndroidManifest.xml에 `android:networkSecurityConfig="@xml/network_security_config"` 추가

---

## 3. 파일 업로드 검증 현황

### 3a. 백엔드 오디오 업로드 검증

#### 파일: `backend/utils/validators.py` (lines 25-53)

```python
ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".ogg"}
ALLOWED_MIME_TYPES = {
    "audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4",
    "audio/x-m4a", "audio/ogg", "audio/vorbis",
}

def validate_audio_format(filename: str, content_type: str | None = None) -> tuple[bool, str]:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return False, (...)
    if content_type and content_type not in ALLOWED_MIME_TYPES:
        if not content_type.startswith("audio/") and content_type != "application/octet-stream":
            return False, (...)
    return True, ""
```

#### 발견사항
- **확장자 검증**: .wav, .mp3, .m4a, .ogg ✅
- **MIME 타입 검증**: content_type 헤더 기반 ✅
- **파일 크기 검증**: 500MB 제한 (`validate_file_size`) ✅
- **매직 바이트 검증**: ❌ 없음 — 클라이언트가 악의적으로 확장자를 .wav로 변경하면 검증 통과
- **`application/octet-stream` 허용**: 일부 클라이언트 호환성 목적이지만 공격 표면 확대

### 3b. 백엔드 템플릿 업로드 검증

#### 파일: `backend/app/api/v1/admin/templates.py` (lines 30-60)

```python
_SUPPORTED_FORMATS = {"docx", "pdf"}
_SUPPORTED_CONTENT_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/pdf",
    "application/octet-stream",
}
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
```

- 확장자 + MIME 타입 + 크기 검증 ✅
- 매직 바이트 검증 ❌

### 3c. 클라이언트 오디오 업로드

#### 파일: `client/lib/services/transcription_api.dart` (lines 21-44)

```dart
Future<Map<String, dynamic>> upload(String filePath, ...) async {
    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath,
        filename: File(filePath).uri.pathSegments.last),
    });
    // ...
}
```

- **클라이언트 검증: ZERO** — 파일 타입, 크기, 확장자 어떤 검증도 없음
- 임의 경로의 임의 파일을 백엔드로 전송

### 3d. 클라이언트 템플릿 업로드

#### 파일: `client/lib/screens/template_screen.dart` (line 46)

```dart
FilePicker.platform.pickFiles(allowedExtensions: ['pdf', 'docx'])
```

- 확장자 필터만 존재, 크기 검증 없음

### 권장 해결책
- **백엔드 매직 바이트 검증**: `python-magic` 또는 직접 시그니처 매칭 구현
  - WAV: `RIFF....WAVE`
  - MP3: `ID3` 또는 `FF FB`
  - M4A: `ftypM4A`
  - OGG: `OggS`
- **클라이언트 사전 검증**: 업로드 전 확장자 + 크기 확인 (불필요한 네트워크 트래픽 방지)

---

## 4. 보안 헤더 현황

### 파일: `backend/app/middleware/security_headers.py` (lines 15-37)

### 현재 헤더
| 헤더 | 값 | 상태 |
|------|-----|------|
| X-Content-Type-Options | nosniff | ✅ |
| X-Frame-Options | DENY | ✅ |
| X-XSS-Protection | 1; mode=block | ✅ |
| Content-Security-Policy | default-src 'none' | ✅ |

### 누락된 헤더
| 헤더 | 권장값 | 이유 |
|------|--------|------|
| Strict-Transport-Security | max-age=31536000; includeSubDomains | HTTPS 강제 (HSTS) |
| Referrer-Policy | strict-origin-when-cross-origin | 리퍼러 정보 유출 방지 |
| Permissions-Policy | camera=(), microphone=(), geolocation=() | 브라우저 API 접근 제한 |

### 참고: X-XSS-Protection
- 모던 브라우저(Chrome 78+)에서 더 이상 사용되지 않음 (deprecated)
- 제거하지는 않으나 CSP가 더 효과적

---

## 5. TLS/HTTPS 배포 현황

### 백엔드 deploy/ 디렉토리
- `setup-ubuntu.sh`: TLS 인증서 설정 없음
- `uvicorn.service`: SSL/TLS 인증서 경로 없음
- 현재 HTTP로 실행, Tailscale 네트워크 보안에 의존

### 권장사항
- HSTS 헤더는 HTTPS 환경에서만 의미 있음
- 프로덕션 배포 시 Let's Encrypt + nginx 리버스 프록시 도입 고려
- 당장은 staging 환경(Tailscale)에서만 사용하므로 HSTS는 프로덕션 환경 감지 후 조건부 적용

---

## 6. 환경 설정 현황

### 파일: `client/lib/config/app_config.dart`

| 환경 | URL | 스키마 |
|------|-----|--------|
| dev | `http://localhost:8000/api/v1` | HTTP |
| staging (기본값) | `http://100.110.255.105:8000/api/v1` | HTTP |
| production | `https://api.voicetextnote.com/api/v1` | HTTPS |

### 발견사항
- **기본 환경이 staging(HTTP)** — dart-define 없이 빌드 시 HTTP 연결
- dev/staging 모두 cleartext HTTP 사용, Tailscale에 의존
- `print()` 에러 로깅이 Release 빌드에서도 활성화

---

## 7. SPEC-SEC-001 분석

### 상태: completed
### 커버 영역:
- API Key 인증 (REQ-SEC-001~005)
- 레이트 리미팅 (REQ-SEC-006~008)
- CORS 정책 (REQ-SEC-009~010)
- 보안 헤더 기초 (REQ-SEC-011): X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- 경로 검증 (FIX-SEC-004)
- CSP (FIX-SEC-005)

### SPEC-SEC-002가 다루지 않을 영역 (중복 방지):
- API Key 인증 로직
- 레이트 리미팅
- CORS 정책
- 기존 보안 헤더 (X-Content-Type-Options 등)

---

## 8. 종합 갭 분석

### 클라이언트 갭
| ID | 갭 | 심각도 | 영역 |
|----|-----|--------|------|
| G1 | NSAllowsArbitraryLoads=true가 Release 빌드에 포함 | Critical | iOS ATS |
| G2 | NSExceptionDomains 없음 | High | iOS ATS |
| G3 | Android network_security_config.xml 없음 | High | Android |
| G4 | 오디오 업로드 클라이언트 검증 없음 | Critical | 파일 처리 |
| G5 | 템플릿 업로드 크기 검증 없음 | Medium | 파일 처리 |
| G7 | print() 로깅이 Release에 포함 | Low | 정보 유출 |
| G8 | 기본 환경이 staging(HTTP) | Medium | 설정 |

### 백엔드 갭
| ID | 갭 | 심각도 | 영역 |
|----|-----|--------|------|
| G-B1 | 매직 바이트 검증 없음 (확장자/MIME만) | High | 파일 검증 |
| G-B2 | HSTS 헤더 없음 | Medium | 보안 헤더 |
| G-B3 | Referrer-Policy, Permissions-Policy 없음 | Low | 보안 헤더 |

---

## 9. 권장 구현 접근법

### 모듈 구성 (최대 5개)

1. **iOS ATS Hardening** (G1, G2): Info.plist 환경 분리, NSExceptionDomains
2. **Android Network Security** (G3): network_security_config.xml 생성
3. **매직 바이트 검증** (G-B1, G4): 백엔드 python-magic 도입 + 클라이언트 사전 검증
4. **보안 헤더 고도화** (G-B2, G-B3): HSTS, Referrer-Policy, Permissions-Policy 추가
5. **클라이언트 파일 검증** (G4, G5, G8): 업로드 전 타입/크기 검증, 기본 환경 안전화

### 기술 제약
- iOS Info.plist 환경 분리는 Xcode xcconfig 또는 Flutter build flavor 필요
- python-magic은 libmagic 시스템 의존성 필요 — 대안으로 순수 Python 매직 바이트 매칭 구현 고려
- HSTS는 HTTPS 환경에서만 적용 가능 — 프로덕션 환경 감지 후 조건부 헤더 적용
