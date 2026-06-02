# SPEC-HISTSYNC-001: Home Screen Meeting History Sync

## Summary

The home screen currently shows only locally stored meetings (SharedPreferences). When a user reinstalls the app or clears local data, all meeting history is lost despite the backend having complete history via `/api/v1/history`. This SPEC adds server-side history sync to the home screen.

## Requirements (EARS Format)

### REQ-HSYNC-001: History API Service
The system SHALL provide a `HistoryApi` Dart service class that calls `GET /api/v1/history` with pagination, task_type filter, and status filter parameters.

### REQ-HSYNC-002: Home Screen Server Sync
When the home screen loads AND SharedPreferences has fewer than the server total, the system SHALL fetch completed meeting history from the server and merge with local state.

### REQ-HSYNC-003: Pull-to-Refresh
When the user pulls down on the home screen meeting list, the system SHALL refresh the meeting list from the server.

### REQ-HSYNC-004: History to Meeting Conversion
The system SHALL convert backend `HistoryItem` (task_id, task_type, status, created_at) into client `Meeting` objects by grouping related task_ids (stt, diarization, minutes, summary) from the same recording session.

### REQ-HSYNC-005: Meeting Deletion
When the user long-presses a meeting card on the home screen, the system SHALL show a delete confirmation dialog and remove the meeting from both local storage and server (DELETE /api/v1/history/{task_id}).

### REQ-HSYNC-006: Loading State
While fetching history from the server, the system SHALL display a loading indicator (shimmer cards) on the home screen.

### REQ-HSYNC-007: Error Handling
If the server sync fails (network error, server down), the system SHALL show a brief snackbar error and continue showing locally stored meetings.

## Acceptance Criteria

- [ ] AC-1: `HistoryApi` service exists with `list()`, `get()`, `delete()` methods
- [ ] AC-2: Home screen loads server history on first launch (empty local state)
- [ ] AC-3: Pull-to-refresh triggers server sync
- [ ] AC-4: Server history items are correctly converted to Meeting objects
- [ ] AC-5: Long-press on meeting card shows delete dialog
- [ ] AC-6: Shimmer loading shown during server fetch
- [ ] AC-7: Offline/error shows snackbar, local data preserved

## Technical Approach

### New Files
- `client/lib/services/history_api.dart` — Backend history API client
- `client/test/services/history_api_test.dart` — Unit tests

### Modified Files
- `client/lib/providers/meeting_list_provider.dart` — Add server sync logic, pull-to-refresh
- `client/lib/screens/home_screen.dart` — Add RefreshIndicator, delete gesture, loading state
- `client/lib/widgets/meeting_card.dart` — Add long-press delete support

### Backend
No backend changes needed. Existing `/api/v1/history` endpoint is sufficient.

### Data Flow
```
App Start → MeetingListNotifier.build()
  → Load SharedPreferences (immediate)
  → Fetch GET /history?task_type=summary&status=completed (async)
  → Merge: server items not in local → add to state
  → Save merged state to SharedPreferences
```

## Out of Scope
- Pagination UI (infinite scroll) — future SPEC
- Offline-first with full SQLite — future SPEC
- Meeting detail editing from history — existing SPEC handles this

---

## Implementation Notes

### 구현 완료 정보

**구현 날짜**: 2026-06-02

**진행 상태**: completed

### 구현된 요구사항

모든 7개 EARS 요구사항 구현 완료:
- **REQ-HSYNC-001**: HistoryApi 서비스 (GET /api/v1/history)
- **REQ-HSYNC-002**: Home screen 서버 동기화 (최초 로드 시)
- **REQ-HSYNC-003**: Pull-to-refresh (당겨 새로고침 제스처)
- **REQ-HSYNC-004**: HistoryItem → Meeting 변환
- **REQ-HSYNC-005**: Long-press 삭제 (홈 화면에서 회의 삭제)
- **REQ-HSYNC-006**: Shimmer 로딩 표시
- **REQ-HSYNC-007**: 에러 핸들링 (Snackbar + 로컬 데이터 보존)

### 주요 구현 결정사항

1. **HistoryApi 서비스**
   - `client/lib/services/history_api.dart`: Backend history API 클라이언트
   - GET /api/v1/history (page, page_size, task_type, status 필터)
   - GET /api/v1/history/{task_id} (단일 항목 조회)
   - DELETE /api/v1/history/{task_id} (항목 삭제)

2. **Home Screen 서버 동기화**
   - `meeting_list_provider.dart`: 최초 로드 시 서버에서 완료된 회의록 가져오기
   - 서버 항목과 로컬 SharedPreferences 병합
   - 병합 결과 다시 SharedPreferences에 저장

3. **Pull-to-Refresh**
   - `home_screen.dart`: RefreshIndicator로 감싸기
   - 당겨 새로고침 시 `MeetingListNotifier.syncFromServer()` 호출
   - Shimmer 카드로 로딩 상태 표시

4. **Meeting 삭제**
   - `meeting_card.dart`: LongPressGestureDetector 추가
   - 삭제 확인 다이얼로그 표시
   - 로컬 SharedPreferences + 서버 DELETE 호출

5. **History to Meeting 변환**
   - 같은 recording_session의 task_id들을 그룹화
   - (stt, diarization, minutes, summary) 완료된 것만 Meeting 객체로 변환
   - task_type='summary'이고 status='completed'인 항목만 표시

---

*SPEC ID: SPEC-HISTSYNC-001*
*생성일: 2026-03-29*
*상태: completed*
