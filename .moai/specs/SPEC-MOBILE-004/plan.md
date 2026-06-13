# Implementation Plan: SPEC-MOBILE-004

## 모바일 프로덕션 완성 — Push 알림 연동, 백그라운드 녹음 강화, 권한 관리 통합, 앱스토어 배포

---

## 개요

SPEC-MOBILE-001 v2.0.0에서 스캐폴드된 모바일 인프라를 **프로덕션 수준으로 완성**한다. 심층 코드 분석 결과, Push 알림 인프라는 코드가 작성되었으나 런타임에서 전혀 연동되지 않은 상태이며, 백그라운드 녹음과 권한 관리에도 중대한 결함이 존재한다. 본 SPEC은 이를 수정하고 App Store 배포 준비까지 완수한다.

**선행 SPEC**: SPEC-MOBILE-001 (completed, v2.0.0 Phase A/B/C)
**개발 방법론**: TDD (Red-Green-Refactor, quality.yaml 설정)

---

## 요구사항 모듈 (5개)

### REQ-MOBILE-004-001: Push 알림 런타임 연동 [P0-CRITICAL]

**EARS**: 회의록 처리 파이프라인이 완료되었을 때, 시스템은 FCM Push 알림을 실제로 전송하고 클라이언트에서 수신하여 해당 회의록 화면으로 딥링크 네비게이션해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 001-01 | `main.dart`에서 앱 시작 시 `NotificationNotifier.initialize()`를 호출하여 FCM을 초기화한다 | P0 |
| 001-02 | FCM 토큰 획득 후 `POST /api/v1/devices/register`로 백엔드에 등록한다 (api_client 통합) | P0 |
| 001-03 | `registerFCMBackgroundHandler()`를 호출하여 백그라운드 메시지 핸들러를 등록한다 | P0 |
| 001-04 | `DeepLinkService.handleBackgroundResume()`과 `handleUrlScheme()`을 main.dart에 연동한다 | P1 |
| 001-05 | 백엔드 `push_service.py`에서 MOCK 코드를 제거하고 실제 Firebase Admin SDK FCM 전송을 활성화한다 | P0 |
| 001-06 | `backend/app/config.py`에 `FIREBASE_CREDENTIALS_PATH` 설정 필드를 추가한다 | P0 |
| 001-07 | Celery 파이프라인 태스크 완료/실패 지점에 `on_pipeline_success/on_failure` hook을 연동한다 | P0 |
| 001-08 | `flutter_local_notifications` Android 알림 채널을 생성한다 (Push 알림 표시용) | P1 |

### REQ-MOBILE-004-002: 백그라운드 녹음 복원력 강화 [P1]

**EARS**: 사용자가 백그라운드 녹음 중 앱이 시스템에 의해 종료되었을 때, 시스템은 녹음 파일 경로를 복원하고 녹음 데이터를 손실 없이 보존해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 002-01 | 녹음 시작 시 파일 경로를 `SharedPreferences`에 저장하고, 녹음 중 10초 간격으로 업데이트한다 | P1 |
| 002-02 | 앱 재시작 시 미완료 녹음을 감지하고 사용자에게 복원 옵션을 제공한다 | P1 |
| 002-03 | `RecordingProvider`에 `pauseRecording()` / `resumeRecording()` 메서드를 구현한다 | P2 |
| 002-04 | Android `RecordingService.flushRecording`에 실제 파일 flush 로직을 구현한다 | P1 |
| 002-05 | 백그라운드 녹음 완료 시 자동 업로드를 트리거한다 (workmanager 또는 Foreground Service 확장) | P2 |

### REQ-MOBILE-004-003: 권한 관리 통합 및 버그 수정 [P0]

**EARS**: 앱이 실행될 때, 시스템은 모든 필요한 플랫폼 권한을 통합적으로 관리하고, 권한 거부 시 안전하게 안내해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 003-01 | `permission_dialog.dart:145-168`의 `openAppSettings()` 무한 재귀 버그를 수정한다 | P0 |
| 003-02 | `PermissionService`에 저장공간/미디어 접근 권한을 추가한다 (`Permission.storage`, `Permission.audio`) | P1 |
| 003-03 | Android에서 권한 요청 전 rationale 다이얼로그를 표시하는 플로우를 추가한다 | P2 |
| 003-04 | 설정 앱에서 돌아온 후 권한 상태를 재확인하는 로직을 추가한다 | P1 |
| 003-05 | iOS/Android 네이티브 메모리/저장공간 확인 Platform Channel을 구현한다 (Dart fallback 대체) | P2 |

### REQ-MOBILE-004-004: App Store 배포 준비 (Phase D) [P2]

**EARS**: 앱이 앱 스토어에 제출될 때, 시스템은 App Store / Google Play 가이드라인에 부합하는 메타데이터와 스크린샷을 포함해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 004-01 | App Store Connect 앱 정보(이름, 설명, 카테고리, 키워드) 메타데이터를 작성한다 | P2 |
| 004-02 | Google Play Console 앱 정보 메타데이터를 작성한다 | P2 |
| 004-03 | 디바이스별 스크린샷 촬영 가이드를 작성한다 (iPhone 6.7", 5.5", iPad 12.9", Android 다양한 크기) | P2 |
| 004-04 | 개인정보 처리방침(Privacy Policy) 페이지/URL을 설정한다 | P2 |
| 004-05 | iOS ATS(App Transport Security) 예외 사유를 문서화한다 (Tailscale HTTP 접속) | P2 |
| 004-06 | Android ProGuard/R8 난독화 규칙을 설정한다 (whisper_ggml_plus, firebase 네이티브 라이브러리 보호) | P2 |

### REQ-MOBILE-004-005: Firebase E2E 통합 검증 (Phase E) [P1]

**EARS**: Firebase 프로젝트가 설정되었을 때, 시스템은 Push 알림의 end-to-end 흐름을 실기기에서 검증해야 한다.

| ID | 요구사항 | 우선순위 |
|----|---------|---------|
| 005-01 | Firebase Console 프로젝트 생성 및 iOS/Android 앱 등록 절차를 문서화한다 | P1 |
| 005-02 | 서비스 계정 키 발급 및 백엔드 환경변수 등록 절차를 문서화한다 | P1 |
| 005-03 | APNs 인증서(.p8) 발급 및 Firebase 연동 절차를 문서화한다 | P1 |
| 005-04 | `GoogleService-Info.plist` (iOS) 및 `google-services.json` (Android) 설정 가이드를 작성한다 | P1 |
| 005-05 | 실기기 E2E 테스트 체크리스트를 작성한다 (녹음 → 업로드 → Push 수신 → 딥링크) | P1 |
| 005-06 | device_tokens DB 마이그레이션 실행 검증 (`alembic upgrade head`) | P1 |

---

## 기술 스택

### 클라이언트 (기존 + 추가)
- Flutter 3.24+ / Dart 3.5+
- Riverpod 2.6+, go_router 15.1+
- `firebase_messaging` ^15.1.0, `flutter_local_notifications` ^18.0.0
- `permission_handler` ^11.3.0, `audio_session` ^0.1.21
- `shared_preferences` ^2.3+ (녹음 경로 복원용, 이미 의존성에 있을 가능성 높음)
- `workmanager` ^0.5+ (백그라운드 업로드, 신규 추가 검토)

### 백엔드 (기존 + 활성화)
- `firebase-admin>=6.0` (이미 pyproject.toml에 선언됨)
- FastAPI, Celery, PostgreSQL, Redis (기존)
- `push_service.py`, `celery_push_hooks.py` (기존, 활성화 필요)

---

## 작업 분해 (Task Decomposition)

### Phase 1: 크리티컬 버그 수정 및 Push 연동 (P0)
- T-001: `permission_dialog.dart` 무한 재귀 버그 수정 + 회귀 테스트
- T-002: `main.dart`에 `NotificationNotifier.initialize()` 연동
- T-003: FCM 토큰 → 백엔드 등록 흐름 구현 (api_client 통합)
- T-004: `registerFCMBackgroundHandler()` 호출 추가
- T-005: `DeepLinkService` 핸들러 연동 (background resume, URL scheme)
- T-006: 백엔드 `push_service.py` MOCK → 실제 FCM 전송 활성화
- T-007: `config.py`에 Firebase 설정 필드 추가
- T-008: Celery 태스크에 push hook 연동

### Phase 2: 백그라운드 녹음 강화 (P1)
- T-009: 녹음 경로 SharedPreferences 저장/복원 구현
- T-010: 앱 재시작 시 미완료 녹음 감지 UI
- T-011: Android `flushRecording` 실제 구현
- T-012: `RecordingProvider` pause/resume 구현

### Phase 3: 권한 관리 완성 (P1)
- T-013: `PermissionService` 저장공간 권한 추가
- T-014: Android rationale-before-request 플로우
- T-015: 설정 앱 복귀 후 권한 재확인 로직

### Phase 4: App Store 준비 (P2)
- T-016: App Store / Google Play 메타데이터 템플릿
- T-017: 스크린샷 가이드 + Privacy Policy
- T-018: ATS 문서화 + ProGuard 규칙

### Phase 5: Firebase E2E (P1)
- T-019: Firebase 설정 절차 문서
- T-020: 실기기 E2E 테스트 체크리스트
- T-021: DB 마이그레이션 검증

---

## 위험 분석

| 위험 | 확률 | 영향 | 완화 |
|------|------|------|------|
| Firebase 프로젝트 미생성으로 E2E 불가 | 높음 | 중간 | 코드 wiring은 완료, Firebase 설정은 문서화 |
| Celery hook 연동이 기존 파이프라인에 영향 | 중간 | 높음 | 기존 회귀 테스트로 검증 |
| iOS 실기기 부재 | 높음 | 중간 | 시뮬레이터 한계 명시, 체크리스트 제공 |
| workmanager 신규 의존성 호환성 | 낮음 | 중간 | 기존 Foreground Service 패턴 우선 검토 |

---

## 검증 전략

1. **단위 테스트**: 각 수정/추가 로직에 대한 TDD 테스트 (quality.yaml: 80% per commit)
2. **통합 테스트**: Push 알림 흐름 (client → backend → FCM mock → client)
3. **회귀 테스트**: 기존 55개 Flutter 테스트 + 3621개 백엔드 테스트 통과
4. **수동 E2E 체크리스트**: 실기기에서 Push/백그라운드 녹음 검증 (Phase 5)

---

*작성일: 2026-06-13*
*작성자: Sisyphus*
*상태: draft (사용자 승인 대기)*
