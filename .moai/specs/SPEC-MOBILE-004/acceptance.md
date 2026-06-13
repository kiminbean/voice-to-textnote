# Acceptance Criteria: SPEC-MOBILE-004

## 모바일 프로덕션 완성 — 인수 테스트 시나리오

---

## REQ-MOBILE-004-001: Push 알림 런타임 연동

### AC-001-01: NotificationNotifier 초기화

```gherkin
Feature: FCM 초기화

  Scenario: 앱 시작 시 FCM이 초기화된다
    Given 클라이언트 앱이 실행 중이다
    When main.dart의 초기화 시퀀스가 실행된다
    Then NotificationNotifier.initialize()가 호출된다
    And FirebaseMessaging 인스턴스가 생성된다
    And flutter_local_notifications 플러그인이 초기화된다
    And 포그라운드 메시지 핸들러가 등록된다

  Scenario: 백그라운드 FCM 핸들러가 등록된다
    Given 앱이 시작된 직후이다
    When registerFCMBackgroundHandler()가 호출된다
    Then FirebaseMessaging.onBackgroundMessage에 핸들러가 등록된다
    And 백그라운드 isolate에서 수신된 메시지가 처리된다
```

### AC-001-02: FCM 토큰 백엔드 등록

```gherkin
Feature: FCM 토큰 등록

  Scenario: FCM 토큰이 백엔드에 등록된다
    Given 사용자가 로그인한 상태이다
    And FCM 토큰이 발급되었다
    When fcmTokenProvider가 토큰을 방출한다
    Then POST /api/v1/devices/register가 호출된다
    And 요청 본문에 fcm_token, platform, user_id가 포함된다
    And 응답으로 device_id를 받는다

  Scenario: 토큰 등록 실패 시 재시도한다
    Given 네트워크가 불안정하다
    When 디바이스 등록 요청이 실패한다
    Then 지수 백오프로 재시도한다 (최대 3회)
    And 최종 실패 시 로그를 남기고 다음 앱 시작 시 재시도한다
```

### AC-001-03: 백엔드 FCM 전송 활성화

```gherkin
Feature: 백엔드 Push 전송

  Scenario: PushService가 실제 FCM을 전송한다
    Given FIREBASE_CREDENTIALS_PATH가 설정되어 있다
    And 서비스 계정 키 파일이 존재한다
    When PushService.send_to_user(user_id, meeting_id, "success")가 호출된다
    Then firebase_admin.messaging.send()가 호출된다
    And 전송 결과(True/False)를 반환한다
    And [MOCK] 로그가 출력되지 않는다

  Scenario: Celery 파이프라인 완료 시 Push가 발송된다
    Given 회의록 처리 Celery 태스크가 성공적으로 완료되었다
    When 태스크의 on_success 콜백이 실행된다
    Then on_pipeline_success(meeting_id, user_id)가 호출된다
    And PushService를 통해 FCM Push 알림이 전송된다

  Scenario: Celery 파이프라인 실패 시 에러 Push가 발송된다
    Given 회의록 처리 Celery 태스크가 실패했다
    When 태스크의 on_failure 콜백이 실행된다
    Then on_pipeline_failure(meeting_id, user_id, error)가 호출된다
    And PushService를 통해 에러 Push 알림이 전송된다
```

### AC-001-04: 딥링크 핸들러 연동

```gherkin
Feature: 딥링크 네비게이션

  Scenario: 백그라운드에서 Push 알림 탭 시 딥링크된다
    Given 앱이 백그라운드에 있다
    When 사용자가 Push 알림을 탭한다
    Then DeepLinkService.handleBackgroundResume()이 호출된다
    And message.data['meeting_id']를 추출한다
    And go_router가 /summary/{meetingId}로 이동한다

  Scenario: URL Scheme으로 앱이 실행된다
    Given 외부 링크 voicetextnote://summary/123이 클릭되었다
    When DeepLinkService.handleUrlScheme()이 호출된다
    Then go_router가 /summary/123으로 이동한다

  Scenario: 유효하지 않은 딥링크는 에러 화면으로 fallback한다
    Given Push 알림의 meeting_id가 존재하지 않는다
    When 딥링크 처리가 시도된다
    Then 에러 화면이 표시된다
    And "회의록을 찾을 수 없습니다" 메시지가 표시된다
```

---

## REQ-MOBILE-004-002: 백그라운드 녹음 복원력 강화

### AC-002-01: 녹음 경로 영속 저장

```gherkin
Feature: 녹음 경로 복원

  Scenario: 녹음 시작 시 경로가 저장된다
    Given 사용자가 녹음을 시작한다
    When RecordingProvider.startRecording()이 호출된다
    Then SharedPreferences에 recording_path가 저장된다
    And SharedPreferences에 recording_started_at이 저장된다

  Scenario: 녹음 중 진행 상태가 주기적으로 업데이트된다
    Given 백그라운드 녹음이 진행 중이다
    When 10초 간격 타이머가 실행된다
    Then SharedPreferences의 recording_elapsed가 업데이트된다
```

### AC-002-02: 앱 재시작 시 녹음 복원

```gherkin
Feature: 미완료 녹음 복원

  Scenario: 앱 재시작 시 미완료 녹음을 감지한다
    Given 이전 세션에서 녹음이 중단되지 않은 채 앱이 종료되었다
    And SharedPreferences에 recording_path가 존재한다
    When 앱이 재시작된다
    Then RecordingProvider가 저장된 경로를 감지한다
    And 복원 다이얼로그가 표시된다: "이전 녹음이 있습니다. (XX분)"

  Scenario: 사용자가 녹음 복원을 선택한다
    Given 복원 다이얼로그가 표시된다
    When 사용자가 [복원]을 선택한다
    Then 저장된 .m4a 파일의 존재가 확인된다
    And 파일이 유효하면 업로드 옵션이 표시된다

  Scenario: 사용자가 녹음 삭제를 선택한다
    Given 복원 다이얼로그가 표시된다
    When 사용자가 [삭제]를 선택한다
    Then SharedPreferences에서 recording 관련 키가 제거된다
    And .m4a 파일이 삭제된다
```

### AC-002-03: Android flushRecording 실제 구현

```gherkin
Feature: Android 파일 flush

  Scenario: flushRecording이 실제로 파일을 flush한다
    Given Android 기기에서 백그라운드 녹음 중이다
    When MethodChannel "flushRecording"이 호출된다
    Then RecordingService가 녹음 파일을 디스크에 강제 flush한다
    And result.success(true)를 반환한다 (no-op이 아님)
```

---

## REQ-MOBILE-004-003: 권한 관리 통합 및 버그 수정

### AC-003-01: 무한 재귀 버그 수정

```gherkin
Feature: openAppSettings 안전 호출

  Scenario: 알림 권한 거부 후 설정 이동이 정상 작동한다
    Given 사용자가 알림 권한을 영구 거부했다 (permanentlyDenied)
    When PermanentlyDeniedDialog에서 "설정으로 이동" 버튼을 탭한다
    Then PermissionService.openAppSettings()가 호출된다
    And 시스템 설정 앱이 열린다
    And 스택 오버플로우가 발생하지 않는다

  Scenario: 로컬 openAppSettings 함수가 PermissionService 메서드를 가리지 않는다
    Given permission_dialog.dart 위젯이 빌드된다
    When openAppSettingsIOS()가 호출된다
    Then PermissionService.openAppSettings()로 위임한다
    And 자기 자신을 재귀 호출하지 않는다
```

### AC-003-02: 저장공간 권한 추가

```gherkin
Feature: 저장공간 권한

  Scenario: Android 13+에서 미디어 접근 권한을 요청한다
    Given Android 13+ (API 33+) 기기이다
    And 오디오 파일 접근이 필요하다
    When PermissionService.requestStoragePermission()이 호출된다
    Then Permission.audio 권한이 요청된다
    And 권한 상태가 반환된다
```

### AC-003-03: 설정 복귀 후 권한 재확인

```gherkin
Feature: 권한 재확인

  Scenario: 설정 앱에서 돌아온 후 권한을 재확인한다
    Given 사용자가 설정 앱으로 이동했다
    When 앱이 다시 foreground로 돌아온다 (AppLifecycleState.resumed)
    Then WidgetsBindingObserver.didChangeAppLifecycleState가 트리거된다
    And 현재 권한 상태를 다시 확인한다
    And 권한이 허용되면 녹음 화면을 활성화한다
    And 권한이 여전히 거부되면 다이얼로그를 유지한다
```

---

## REQ-MOBILE-004-004: App Store 배포 준비

### AC-004-01: App Store 메타데이터

```gherkin
Feature: App Store 메타데이터

  Scenario: App Store Connect 등록 정보가 준비된다
    Given docs/app-store-metadata.md가 작성된다
    When 메타데이터를 검토한다
    Then 앱 이름, 부제, 설명, 카테고리, 키워드가 포함된다
    And 한국어 및 영어 메타데이터가 포함된다
    And Privacy Policy URL이 포함된다
```

### AC-004-02: ATS 예외 문서화

```gherkin
Feature: ATS 문서화

  Scenario: iOS ATS 예외 사유가 문서화된다
    Given Tailscale HTTP 접속으로 인해 ATS 예외가 필요하다
    When ATS 문서를 검토한다
    Then 예외 대상 도메인(Tailscale IP)이 명시된다
    And ATS 예외 사유(justification)가 기재된다
    And App Store 심사용 설명이 포함된다
```

---

## REQ-MOBILE-004-005: Firebase E2E 통합 검증

### AC-005-01: Firebase 설정 문서

```gherkin
Feature: Firebase 설정 가이드

  Scenario: Firebase 프로젝트 생성 절차가 문서화된다
    Given docs/firebase-setup-guide.md가 작성된다
    When 설정 절차를 따른다
    Then 프로젝트 생성, iOS/Android 앱 등록 단계가 포함된다
    And GoogleService-Info.plist 다운로드 및 배치 방법이 포함된다
    And google-services.json 다운로드 및 배치 방법이 포함된다
    And 서비스 계정 키 발급 및 FIREBASE_CREDENTIALS_PATH 설정이 포함된다
    And APNs 인증서(.p8) 발급 및 Firebase 업로드 방법이 포함된다
```

### AC-005-02: 실기기 E2E 테스트 체크리스트

```gherkin
Feature: 실기기 E2E 테스트

  Scenario: Push 알림 E2E 흐름이 검증된다
    Given Firebase 프로젝트가 설정되었다
    And 실기기에 앱이 설치되었다
    And device_tokens DB 마이그레이션이 실행되었다 (alembic upgrade head)
    When 사용자가 녹음 → 업로드 → 처리 대기를 수행한다
    Then Celery 파이프라인 완료 시 Push 알림이 수신된다
    And Push 알림 탭 시 회의록 상세 화면으로 이동한다
    And 처리 실패 시 에러 Push 알림이 수신된다

  Scenario: 백그라운드 녹음 E2E 흐름이 검증된다
    Given 실기기에서 녹음을 시작한다
    When 앱을 백그라운드로 전환한다
    Then 녹음이 계속 진행된다
    And 상태바에 녹음 인디케이터가 표시된다
    When 앱을 강제 종료 후 재시작한다
    Then 복원 다이얼로그가 표시된다
    And 저장된 녹음 파일을 복원할 수 있다
```

---

## 품질 게이트 (Quality Gates)

### 코드 품질

| 게이트 | 기준 | 검증 방법 |
|--------|------|----------|
| 기존 테스트 회귀 | 3621개 백엔드 테스트 + 55개 Flutter 테스트 모두 통과 | `pytest backend/` + `flutter test` |
| 신규 코드 커버리지 | 80% 이상 (quality.yaml min_coverage_per_commit) | `pytest --cov` + `flutter test --coverage` |
| LSP 에러 | 0 errors, 0 type errors (quality.yaml run gate) | `flutter analyze` + `mypy backend/` |
| 린트 | 0 errors | `ruff check backend/` + `dart format` |

### TRUST 5 프레임워크

| 항목 | 기준 |
|------|------|
| Tested | 모든 신규 로직에 단위 테스트 작성 (TDD) |
| Readable | 네이밍 컨벤션 준수, 코드 주석은 'Why' 중심 |
| Understandable | 복잡도 허용 범위 내, 문서화 완료 |
| Secured | API Key/FCM 토큰 안전 전송, 보안 헤더 유지 |
| Trackable | 구조화된 로깅, 요청 ID 추적 유지 |

---

*작성일: 2026-06-13*
*작성자: Sisyphus*
