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
