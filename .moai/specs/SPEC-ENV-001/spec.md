# SPEC-ENV-001: Flutter 환경 설정 분리

## 메타데이터

| 항목 | 내용 |
|------|------|
| SPEC ID | SPEC-ENV-001 |
| 상태 | IN_PROGRESS |
| 생성일 | 2026-03-29 |
| 담당 | kisoo |
| 우선순위 | MEDIUM |

## 문제 정의

API URL `http://100.110.255.105:8000/api/v1`이 `client/lib/config/app_config.dart`에 하드코딩되어 있다. 코드 변경 없이 개발/스테이징/프로덕션 서버를 전환하는 것이 불가능하다.

## 해결 방안

Dart의 `--dart-define` 컴파일 타임 환경 변수를 사용하여 환경별 API URL을 설정한다.

## 범위

- `AppConfig` 수정: `String.fromEnvironment()`로 환경 변수 읽기, 기본값 유지
- 환경별 실행 스크립트 생성
- 3개 환경 지원: dev (localhost), staging (Tailscale IP), production (미래 도메인)
- Flutter 전용 — 백엔드 변경 없음

## 요구사항 (EARS 형식)

### 기능 요구사항

**REQ-ENV-001** (Event-driven)
The system shall read API base URL from `--dart-define=API_BASE_URL` compile-time variable, with fallback to current hardcoded value `http://100.110.255.105:8000/api/v1`.

**REQ-ENV-002** (Ubiquitous)
The system shall provide an `Environment` enum (dev, staging, production) selectable via `--dart-define=ENV=dev|staging|production`.

**REQ-ENV-003** (State-driven)
While running in non-production environment, the system shall expose `isDebugMode = true` flag for conditional debug behavior.

**REQ-ENV-004** (Ubiquitous)
The system shall provide launch scripts (`run_dev.sh`, `run_staging.sh`, `run_production.sh`) for each environment.

### 비기능 요구사항

**REQ-ENV-005** (Unwanted)
The system shall NOT break existing behavior: default environment is staging with IP `http://100.110.255.105:8000/api/v1`.

**REQ-ENV-006** (Unwanted)
The system shall NOT require `const` qualifier for `apiBaseUrl` (getter is acceptable).

## 수락 기준

- [ ] `flutter test client/test/config/app_config_test.dart` 통과
- [ ] `flutter analyze client/` 경고 없음
- [ ] 기존 테스트 전체 통과 (`flutter test`)
- [ ] dev/staging/production 실행 스크립트 3개 생성

## 기술 설계

### 파일 변경 목록

| 파일 | 변경 유형 | 설명 |
|------|----------|------|
| `client/lib/config/app_config.dart` | MODIFY | 환경 변수 지원 추가 |
| `client/test/config/app_config_test.dart` | CREATE | 명세 테스트 |
| `client/scripts/run_dev.sh` | CREATE | dev 실행 스크립트 |
| `client/scripts/run_staging.sh` | CREATE | staging 실행 스크립트 |
| `client/scripts/run_production.sh` | CREATE | production 실행 스크립트 |

### 환경별 기본 URL

| 환경 | URL |
|------|-----|
| dev | `http://localhost:8000/api/v1` |
| staging | `http://100.110.255.105:8000/api/v1` (현재 값 유지) |
| production | `https://api.voicetextnote.com/api/v1` |

### 기존 코드 영향 분석

`AppConfig.apiBaseUrl` 사용처 (getter로 변경 시 const 제거 필요 없음):
- `client/lib/services/api_client.dart:13` — `baseUrl: AppConfig.apiBaseUrl`
- `client/lib/services/auth_api.dart:13` — `baseUrl: AppConfig.apiBaseUrl`
- `client/lib/screens/processing_screen.dart:55` — `baseUrl: AppConfig.apiBaseUrl`

모두 런타임 값 할당이므로 getter 변환 후에도 동작에 영향 없음.

---

## Implementation Notes

### 구현 완료 정보

**구현 날짜**: 2026-06-02

**진행 상태**: completed

### 구현된 요구사항

모든 6개 EARS 요구사항 구현 완료:
- **REQ-ENV-001**: `--dart-define=API_BASE_URL` 컴파일 타임 변수 지원
- **REQ-ENV-002**: Environment enum (dev, staging, production)
- **REQ-ENV-003**: isDebugMode 플래그 (비프로덕션 환경에서 true)
- **REQ-ENV-004**: 실행 스크립트 3개 (run_dev.sh, run_staging.sh, run_production.sh)
- **REQ-ENV-005**: 기존 동작 유지 (staging 기본값)
- **REQ-ENV-006**: getter 기반 apiBaseUrl (const 불필요)

### 주요 구현 결정사항

1. **Dart 컴파일 타임 환경 변수**
   - `String.fromEnvironment('API_BASE_URL')`로 API URL 읽기
   - `const String.fromEnvironment('ENV')`로 환경 식별
   - 기본값: staging 환경 `http://100.110.255.105:8000/api/v1`

2. **환경별 API URL**
   - dev: `http://localhost:8000/api/v1`
   - staging: `http://100.110.255.105:8000/api/v1` (기존값 유지)
   - production: `https://api.voicetextnote.com/api/v1` (플레이스홀더)

3. **실행 스크립트**
   - `run_dev.sh`: `flutter run --dart-define=ENV=dev --dart-define=API_BASE_URL=http://localhost:8000/api/v1`
   - `run_staging.sh`: `flutter run --dart-define=ENV=staging`
   - `run_production.sh`: `flutter run --dart-define=ENV=production --dart-define=API_BASE_URL=https://api.voicetextnote.com/api/v1`

4. **기존 코드 영향 최소화**
   - `AppConfig.apiBaseUrl`를 getter로 변경 (const 제거)
   - 사용처 3곳 (api_client.dart, auth_api.dart, processing_screen.dart) 모두 런타임 할당이므로 영향 없음

---

*SPEC ID: SPEC-ENV-001*
*생성일: 2026-03-29*
*상태: completed*
