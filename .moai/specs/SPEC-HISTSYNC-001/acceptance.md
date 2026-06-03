# SPEC-HISTSYNC-001: Acceptance Criteria

## Test Scenarios

### AC-1: HistoryApi 서비스 존재

**Given** Flutter 클라이언트 프로젝트가 빌드 가능한 상태
**When** `HistoryApi` 클래스를 import할 때
**Then** `list()`, `get()`, `delete()` 메서드가 정의되어 있어야 함

```dart
// 검증: client/lib/services/history_api.dart
final api = HistoryApi();
expect(api.list, isA<Function>());
expect(api.get, isA<Function>());
expect(api.delete, isA<Function>());
```

**Status**: PASS (구현 완료)

---

### AC-2: 홈 화면 서버 히스토리 로드

**Given** 로컬 SharedPreferences가 비어있는 상태 (앱 최초 설치 또는 재설치)
**And** 서버에 완료된 회의록 5건이 존재함
**When** 홈 화면이 로드될 때
**Then** 서버에서 5건의 회의록을 가져와 화면에 표시해야 함
**And** 가져온 데이터는 SharedPreferences에 저장되어야 함

**Status**: PASS (구현 완료)

---

### AC-3: Pull-to-Refresh 동작

**Given** 홈 화면에 회의록 목록이 표시된 상태
**When** 사용자가 목록을 아래로 당길 때 (pull-to-refresh)
**Then** 서버에서 최신 히스토리를 다시 가져와야 함
**And** 로딩 중 Shimmer 효과가 표시되어야 함

**Status**: PASS (구현 완료)

---

### AC-4: HistoryItem → Meeting 변환

**Given** 서버에서 다음 HistoryItem들이 반환됨:
  - task_type='stt', status='completed', recording_session='abc123'
  - task_type='diarization', status='completed', recording_session='abc123'
  - task_type='summary', status='completed', recording_session='abc123'
**When** 변환 로직이 실행될 때
**Then** 동일 recording_session의 항목들이 하나의 Meeting 객체로 그룹화되어야 함
**And** task_type='summary' && status='completed'인 항목만 표시 대상이어야 함

**Status**: PASS (구현 완료)

---

### AC-5: 미팅 카드 삭제

**Given** 홈 화면에 회의록 카드가 표시된 상태
**When** 사용자가 카드를 길게 누를 때 (long-press)
**Then** 삭제 확인 다이얼로그가 표시되어야 함
**When** 삭제를 확인할 때
**Then** 로컬 SharedPreferences에서 해당 미팅이 제거되어야 함
**And** 서버에 `DELETE /api/v1/history/{task_id}` 요청이 전송되어야 함

**Status**: PASS (구현 완료)

---

### AC-6: Shimmer 로딩 표시

**Given** 서버에서 데이터를 가져오는 중
**When** 네트워크 요청이 진행 중일 때
**Then** Shimmer 카드가 로딩 인디케이터로 표시되어야 함
**And** 기존 로컬 데이터가 있는 경우 로컬 데이터 위에 Shimmer가 오버레이되어야 함

**Status**: PASS (구현 완료)

---

### AC-7: 오프라인/에러 처리

**Given** 네트워크가 연결되지 않은 상태 또는 서버가 응답하지 않는 상태
**And** SharedPreferences에 3건의 로컬 미팅 데이터가 있음
**When** 서버 동기화를 시도할 때
**Then** Snackbar로 에러 메시지가 표시되어야 함
**And** 로컬 3건의 미팅 데이터는 그대로 유지되어야 함
**And** 앱이 크래시되지 않아야 함

**Status**: PASS (구현 완료)

---

## Edge Cases

| Case | Expected Behavior | Status |
|------|-------------------|--------|
| 서버 응답 빈 배열 | 로컬 데이터만 표시, 에러 없음 | PASS |
| 로컬/서버 중복 항목 | 서버 기준으로 병합, 중복 제거 | PASS |
| 매우 많은 히스토리 (100+) | Pagination으로 나누어 로드 | PASS |
| 서버 응답 지연 (5s+) | Shimmer 로딩 표시, 타임아웃 처리 | PASS |
| 삭제 중 네트워크 오류 | 로컬 삭제 후 서버 삭제 재시도 | PASS |

## Quality Gates

| Gate | Criteria | Status |
|------|----------|--------|
| 단위 테스트 | history_api_test.dart 통과 | PASS |
| 위젯 테스트 | home_screen_test.dart 통과 | PASS |
| TRUST 5 | Tested, Readable, Unified, Secured, Trackable | PASS |
| 커버리지 | 85%+ (대상 파일 기준) | PASS |

---

*Acceptance Version: 1.0.0*
*Last Updated: 2026-06-03*
