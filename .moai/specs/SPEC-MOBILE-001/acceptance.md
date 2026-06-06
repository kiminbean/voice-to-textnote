# SPEC-MOBILE-001: 인수 테스트 (v2.0.0)

## AC-001: iOS/Android 앱 아이콘 및 스플래시 표시 [EXISTING]

**Given** 앱이 iOS 또는 Android 디바이스에 설치되어 있을 때
**When** 사용자가 앱을 실행하면
**Then** 커스텀 앱 아이콘이 홈 화면에 표시되고, 앱 시작 시 브랜드 스플래시 스크린이 표시된 후 메인 화면으로 전환된다

**검증 방법**:
- iOS 시뮬레이터/실기기에서 앱 아이콘 확인
- Android 에뮬레이터/실기기에서 앱 아이콘 확인
- 앱 실행 시 스플래시 스크린 표시 후 메인 화면 전환 확인
- 기본 Flutter 아이콘이 아닌 커스텀 아이콘임을 확인

---

## AC-002: Android 빌드 성공 [EXISTING]

**Given** Android 플랫폼이 프로젝트에 추가되어 있을 때
**When** `flutter build apk --release`를 실행하면
**Then** APK 파일이 정상적으로 생성되고, Android 10+ 디바이스에서 설치 및 실행이 가능하다

**검증 방법**:
- `flutter build apk --debug` 빌드 성공 확인
- Android 에뮬레이터 (API 29+)에서 앱 실행 확인
- 녹음 → 업로드 → 결과 확인 기본 플로우 동작 확인

---

## AC-003: 백그라운드 오디오 녹음 지속 [EXISTING]

**Given** 사용자가 녹음을 진행 중일 때
**When** 홈 버튼을 눌러 앱을 백그라운드로 전환하면
**Then** 녹음이 중단되지 않고 계속 진행되며, 앱으로 복귀 시 경과 시간이 정확히 표시된다

**검증 방법**:
- iOS: 녹음 시작 → 홈 화면으로 전환 → 30초 대기 → 앱 복귀 → 경과 시간 30초 이상 확인
- Android: 녹음 시작 → 홈 화면으로 전환 → 상태바에 녹음 Notification 표시 확인 → 앱 복귀 → 경과 시간 확인
- 백그라운드 녹음 후 중지 → 파일 업로드 → STT 결과가 백그라운드 구간 음성을 포함하는지 확인

---

## AC-002-PROD: Push 알림 프로덕션 플로우 [NEW — AC-004 대체]

**Given** 사용자가 오디오를 업로드하고 Celery 파이프라인(STT → Diarization → Summary)이 실행 중일 때
**When** 파이프라인이 완료되면
**Then** Firebase Admin SDK를 통해 사용자 디바이스에 "회의록 처리 완료" Push 알림이 도착하고, 알림 payload에 `meeting_id`가 포함되어 있다

**검증 방법**:
- 실기기에서 녹음 → 업로드 후 앱을 백그라운드로 전환
- 파이프라인 완료 후 Push 알림 수신 확인 (10분 이내)
- 수신된 알림의 `data` payload에 `meeting_id` 필드 포함 확인
- Firebase Admin SDK 전송 로그에서 `meeting_id` 포함 확인
- 포그라운드 상태에서도 `flutter_local_notifications` 배너 표시 확인

**실패 시나리오**:
- 파이프라인 실패 시 `on_failure` hook이 "처리 실패" 알림을 전송하는지 확인
- FCM 토큰이 만료된 경우(UNREGISTERED 응답) DB에서 자동 무효화되는지 확인
- Push 전송 실패 시 파이프라인 자체는 정상 완료되는지 확인 (격리 보장)

---

## AC-005: 권한 거부 시 적절한 UX [EXISTING]

**Given** 사용자가 마이크 권한을 거부한 상태일 때
**When** 녹음 화면에 진입하면
**Then** 녹음 버튼이 비활성화되고, "마이크 권한이 필요합니다" 안내와 함께 설정으로 이동하는 버튼이 표시된다

**검증 방법**:
- iOS: 설정 > 개인정보 보호 > 마이크 > Voice TextNote 끄기 → 앱 진입 → 안내 메시지 확인
- Android: 설정 > 앱 > Voice TextNote > 권한 > 마이크 거부 → 앱 진입 → 안내 메시지 확인
- "설정으로 이동" 버튼 탭 → 시스템 설정 앱 열림 확인
- 권한 재허용 후 앱 복귀 → 녹음 기능 정상 동작 확인

---

## AC-006: FCM 토큰 등록 [EXISTING]

**Given** 앱이 최초 실행되거나 FCM 토큰이 갱신되었을 때
**When** 앱이 시작되면
**Then** FCM 토큰이 백엔드 서버에 자동으로 등록되고, 서버에서 해당 디바이스로 Push를 전송할 수 있다

**검증 방법**:
- 앱 최초 실행 → 서버 로그에서 `POST /api/v1/devices/register` 요청 확인
- 등록된 토큰으로 Firebase Console에서 테스트 Push 전송 → 수신 확인
- 토큰 갱신 시 (앱 재설치 등) 서버에 새 토큰 업데이트 확인

---

## AC-006-DEEP: 딥링크 네비게이션 [NEW]

**Given** Push 알림 또는 외부 URL을 통해 앱에 진입할 때
**When** 사용자가 Push 알림을 탭하거나 `voicetextnote://summary/{meetingId}` URL을 열면
**Then** 앱이 올바른 회의록 상세 화면(`/summary/{meetingId}`)으로 즉시 이동한다

**시나리오별 검증**:

### Cold Start (앱 종료 상태)

**Given** 앱이 완전히 종료된 상태에서
**When** Push 알림을 탭하여 앱이 실행되면
**Then** `FirebaseMessaging.instance.getInitialMessage()`에서 payload를 파싱하여 회의록 상세 화면으로 이동한다

**검증 방법**:
- 앱을 완전 종료 (앱 스위처에서 제거)
- Firebase Console에서 `meeting_id` 포함 테스트 Push 전송
- Push 알림 탭 → 앱 실행 → 회의록 상세 화면 즉시 표시 (스플래시 후 2초 이내)

### Background (앱 백그라운드)

**Given** 앱이 백그라운드에 있는 상태에서
**When** Push 알림을 탭하면
**Then** `onMessageOpenedApp` 스트림에서 payload를 파싱하여 회의록 상세 화면으로 이동한다

**검증 방법**:
- 앱을 백그라운드로 전환
- Push 알림 수신 → 탭 → 회의록 상세 화면 즉시 이동

### Foreground (앱 사용 중)

**Given** 앱을 사용 중인 상태에서
**When** Push 알림이 수신되면
**Then** `flutter_local_notifications`로 배너가 표시되고, 탭 시 회의록 상세 화면으로 이동한다

**검증 방법**:
- 앱 포그라운드 사용 중
- Push 수신 → 로컬 알림 배너 표시 → 탭 → 회의록 화면 이동

### URL Scheme (외부 링크)

**Given** 앱이 설치된 상태에서
**When** 브라우저 또는 다른 앱에서 `voicetextnote://summary/{meetingId}`를 열면
**Then** 앱이 실행되고 회의록 상세 화면으로 이동한다

**검증 방법**:
- iOS: Safari 주소창에 `voicetextnote://summary/test123` 입력 → 앱 열림 → 화면 이동
- Android: `adb shell am start -a android.intent.action.VIEW -d "voicetextnote://summary/test123"` → 화면 이동

### 에러 케이스

**Given** 딥링크 대상 meetingId가 존재하지 않거나 유효하지 않을 때
**When** 딥링크로 앱이 열리면
**Then** 앱이 crash되지 않고 "회의록을 찾을 수 없습니다" 에러 화면으로 fallback한다

**검증 방법**:
- 존재하지 않는 meetingId로 딥링크 열기 → 에러 화면 표시
- 빈 meetingId로 디링크 열기 → 에러 화면 표시
- 잘못된 형식의 URL → 에러 화면 표시

---

## AC-007-PERSIST: 디바이스 등록 영속성 [NEW]

**Given** 사용자가 FCM 토큰을 등록했을 때
**When** 백엔드 서버가 재시작되면
**Then** 등록된 FCM 토큰이 PostgreSQL `device_tokens` 테이블에서 유지되어 Push 알림 전송이 가능하다

**검증 방법**:
- 앱에서 FCM 토큰 등록 → DB에서 레코드 확인
- 백엔드 서버 재시작 → DB에서 동일 레코드 존재 확인
- 서버 재시작 후 Push 알림 전송 → 정상 수신 확인
- 동일 토큰 재등록 시 UPSERT 동작 (새 레코드 생성 아님) 확인

**엣지 케이스**:
- 동일 사용자가 여러 기기에서 로그인 → 각 기기 토큰이 모두 저장되는지 확인
- 오래된 토큰(FCM UNREGISTERED 응답) → 자동 무효화(`is_active=false`) 확인
- 무효화된 토큰으로는 Push 미전송 확인

---

## AC-008: 앱 강제 종료 후 녹음 파일 보존 [EXISTING]

**Given** 사용자가 녹음 중일 때
**When** 시스템이 앱을 강제 종료(kill)하면
**Then** 강제 종료 시점까지의 녹음 데이터가 파일로 보존되어 있고, 앱 재시작 시 미완료 녹음 파일을 감지한다

**검증 방법**:
- 녹음 시작 → 60초 이상 녹음 → 앱 강제 종료 (Xcode/ADB에서 kill)
- 앱 재시작 → 미완료 녹음 파일 감지 안내 확인
- 보존된 파일 재생 → 강제 종료 시점까지의 음성 포함 확인

---

## 플랫폼별 테스트 시나리오

### iOS (실기기 필수 — Push 알림)

| 시나리오 | 단계 | 기대 결과 |
|----------|------|----------|
| Push 수신 (foreground) | 녹음 업로드 → 앱 유지 → 완료 대기 | 로컬 알림 배너 표시 |
| Push 수신 (background) | 녹음 업로드 → 홈 화면 → 완료 대기 | 시스템 알림 배너 → 탭 → 회의록 화면 |
| Push 수신 (cold start) | 앱 종료 → Push 탭 | 앱 실행 → 회의록 화면 |
| 백그라운드 녹음 | 녹음 중 → 홈 → 30초 → 복귀 | 오렌지 도트 표시, 녹음 지속 |
| URL Scheme | Safari에서 `voicetextnote://summary/x` | 앱 열림 → 회의록 화면 |
| 권한 거부 | 설정에서 마이크 거부 → 앱 진입 | 안내 다이얼로그 + 설정 이동 |

### Android (실기기 필수 — Push 알림)

| 시나리오 | 단계 | 기대 결과 |
|----------|------|----------|
| Push 수신 (foreground) | 녹음 업로드 → 앱 유지 → 완료 대기 | 로컬 알림 배너 표시 |
| Push 수신 (background) | 녹음 업로드 → 홈 → 완료 대기 | 시스템 알림 → 탭 → 회의록 화면 |
| Push 수신 (cold start) | 앱 종료 → Push 탭 | 앱 실행 → 회의록 화면 |
| 백그라운드 녹음 | 녹음 중 → 홈 → 30초 → 복귀 | Notification 표시, 녹음 지속 |
| URL Scheme | ADB intent → `voicetextnote://summary/x` | 앱 열림 → 회의록 화면 |
| 권한 거부 | 설정에서 마이크/알림 거부 → 앱 진입 | 안내 다이얼로그 + 설정 이동 |

---

## Quality Gates

### 빌드 품질

| 항목 | 기준 |
|------|------|
| iOS 빌드 | `flutter build ios --release` 성공 (경고 0개) |
| Android 빌드 | `flutter build apk --release` 성공 (경고 0개) |
| 정적 분석 | `dart analyze` 오류 0개 |
| 테스트 | `flutter test` 전체 통과 |

### 런타임 품질

| 항목 | 기준 |
|------|------|
| 백그라운드 녹음 지속 시간 | iOS/Android 모두 최소 30분 이상 |
| Push 알림 지연 | 파이프라인 완료 후 10초 이내 수신 |
| 콜드 스타트 딥링크 | 스플래시 포함 3초 이내 타겟 화면 도달 |
| 앱 시작 시간 | 스플래시 포함 3초 이내 (cold start) |
| 메모리 사용량 | 녹음 중 200MB 미만 |
| Push 전송 실패 격리 | Push 실패 시 파이프라인 완료에 영향 없음 |

### DB Persistence 품질

| 항목 | 기준 |
|------|------|
| 토큰 저장 | 등록 요청 후 DB 레코드 존재 확인 |
| 서버 재시작 후 유지 | 재시작 후 동일 토큰 조회 가능 |
| UPSERT 동작 | 동일 토큰 재등록 시 레코드 갱신 (중복 생성 없음) |
| 무효화 | FCM UNREGISTERED 응답 후 `is_active=false` 설정 |
| 다중 기기 | 동일 사용자의 여러 기기 토큰 모두 활성 유지 |

### 권한 UX

| 항목 | 기준 |
|------|------|
| 권한 요청 시점 | 기능 사용 직전 (lazy permission) |
| 권한 거부 안내 | 모든 필수 권한에 대해 안내 다이얼로그 존재 |
| 설정 이동 | "다시 묻지 않기" 상태에서 설정 앱 이동 기능 동작 |
