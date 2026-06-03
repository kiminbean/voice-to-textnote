# SPEC-ENV-001: Implementation Plan

## Overview

API URL이 하드코딩된 Flutter 클라이언트에 Dart `--dart-define` 컴파일 타임 환경 변수를 도입하여 개발/스테이징/프로덕션 환경을 코드 변경 없이 전환 가능하게 함.

## Implementation Status: COMPLETED (2026-06-02)

## Technology Stack

| Component | Technology | Usage |
|-----------|-----------|-------|
| Env Variables | Dart `--dart-define` | 컴파일 타임 환경 변수 |
| Config | `String.fromEnvironment()` | 환경 변수 읽기 |
| State | Riverpod | 환경 설정 관리 |

## Task Decomposition

### Task 1: AppConfig 환경 변수 지원 (REQ-ENV-001)
- **File**: `client/lib/config/app_config.dart`
- **Status**: COMPLETED
- `String.fromEnvironment('API_BASE_URL')`로 API URL 읽기
- 기본값: staging `http://100.110.255.105:8000/api/v1`

### Task 2: Environment Enum (REQ-ENV-002)
- **File**: `client/lib/config/app_config.dart`
- **Status**: COMPLETED
- `Environment` enum: dev, staging, production
- `--dart-define=ENV=dev|staging|production`로 선택

### Task 3: Debug Mode 플래그 (REQ-ENV-003)
- **File**: `client/lib/config/app_config.dart`
- **Status**: COMPLETED
- 비프로덕션 환경에서 `isDebugMode = true`

### Task 4: 실행 스크립트 생성 (REQ-ENV-004)
- **Files**: `client/scripts/run_dev.sh`, `run_staging.sh`, `run_production.sh`
- **Status**: COMPLETED

### Task 5: 기존 동작 유지 (REQ-ENV-005)
- **Status**: COMPLETED
- 기본 환경 = staging, 기본 URL = 기존값 유지

### Task 6: Getter 기반 apiBaseUrl (REQ-ENV-006)
- **File**: `client/lib/config/app_config.dart`
- **Status**: COMPLETED
- const 대신 getter 사용

## Risk Analysis

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| 기존 동작 변경 | High | 기본값 = staging (기존값) | Resolved |
| 사용처 호환성 | Medium | 3곳 모두 런타임 할당이라 영향 없음 | Resolved |
| 빌드 시 환경 변수 누락 | Low | 기본값 제공으로 graceful fallback | Resolved |

## Environment Configuration

| 환경 | URL | 스크립트 |
|------|-----|---------|
| dev | `http://localhost:8000/api/v1` | run_dev.sh |
| staging | `http://100.110.255.105:8000/api/v1` | run_staging.sh |
| production | `https://api.voicetextnote.com/api/v1` | run_production.sh |

## Affected Files (No Breaking Changes)

- `client/lib/services/api_client.dart:13` — `baseUrl: AppConfig.apiBaseUrl`
- `client/lib/services/auth_api.dart:13` — `baseUrl: AppConfig.apiBaseUrl`
- `client/lib/screens/processing_screen.dart:55` — `baseUrl: AppConfig.apiBaseUrl`

모두 런타임 값 할당이므로 getter 변환 후에도 동작에 영향 없음.

---

*Plan Version: 1.0.0*
*Last Updated: 2026-06-03*
