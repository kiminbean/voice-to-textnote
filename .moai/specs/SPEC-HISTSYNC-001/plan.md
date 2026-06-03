# SPEC-HISTSYNC-001: Implementation Plan

## Overview

홈 화면에 서버 기반 미팅 히스토리 동기화 기능 추가. 기존 SharedPreferences 기반 로컬 저장만 있던 홈 화면에 백엔드 `/api/v1/history` API를 연동하여 재설치/데이터 삭제 후에도 히스토리 복원 가능.

## Implementation Status: COMPLETED (2026-06-02)

## Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| HTTP Client | Dio | latest |
| State Management | Riverpod | latest |
| Local Storage | SharedPreferences | latest |
| Backend API | FastAPI | existing |

## Architecture

### Data Flow

```
App Start → MeetingListNotifier.build()
  → Load SharedPreferences (immediate)
  → Fetch GET /history?task_type=summary&status=completed (async)
  → Merge: server items not in local → add to state
  → Save merged state to SharedPreferences
```

### API Integration

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/history` | GET | 목록 조회 (pagination, filter 지원) |
| `/api/v1/history/{task_id}` | GET | 단일 항목 조회 |
| `/api/v1/history/{task_id}` | DELETE | 항목 삭제 |

### Task Decomposition

#### Task 1: HistoryApi Service (REQ-HSYNC-001)
- **File**: `client/lib/services/history_api.dart`
- **Test**: `client/test/services/history_api_test.dart`
- **Status**: COMPLETED
- Backend history API 클라이언트 구현
- pagination, task_type, status 필터 파라미터 지원

#### Task 2: Home Screen Server Sync (REQ-HSYNC-002)
- **File**: `client/lib/providers/meeting_list_provider.dart`
- **Status**: COMPLETED
- 최초 로드 시 서버에서 완료된 회의록 가져오기
- SharedPreferences + 서버 데이터 병합 로직

#### Task 3: Pull-to-Refresh (REQ-HSYNC-003)
- **File**: `client/lib/screens/home_screen.dart`
- **Status**: COMPLETED
- RefreshIndicator로 당겨 새로고침 구현
- `MeetingListNotifier.syncFromServer()` 호출

#### Task 4: History → Meeting 변환 (REQ-HSYNC-004)
- **File**: `client/lib/services/history_api.dart`
- **Status**: COMPLETED
- 같은 recording_session의 task_id 그룹화
- task_type='summary' && status='completed' 필터링

#### Task 5: Meeting 삭제 (REQ-HSYNC-005)
- **File**: `client/lib/widgets/meeting_card.dart`
- **Status**: COMPLETED
- LongPressGestureDetector 추가
- 삭제 확인 다이얼로그 + 로컬/서버 동시 삭제

#### Task 6: Loading State (REQ-HSYNC-006)
- **File**: `client/lib/screens/home_screen.dart`
- **Status**: COMPLETED
- Shimmer 카드 로딩 표시

#### Task 7: Error Handling (REQ-HSYNC-007)
- **File**: `client/lib/providers/meeting_list_provider.dart`
- **Status**: COMPLETED
- 네트워크 오류 시 Snackbar 표시
- 로컬 데이터 보존

## Risk Analysis

| Risk | Impact | Mitigation | Status |
|------|--------|------------|--------|
| 네트워크 오류 시 빈 화면 | High | 로컬 캐시 우선 표시 + Snackbar | Resolved |
| 대량 히스토리 로딩 지연 | Medium | Pagination + Shimmer 로딩 | Resolved |
| 서버-로컬 데이터 불일치 | Medium | 병합 로직 (서버 기준 + 로컬 보완) | Resolved |

## Out of Scope

- Pagination UI (무한 스크롤) — future SPEC
- Offline-first SQLite — future SPEC
- 미팅 상세 편집 — 기존 SPEC 처리

## MX Tag Plan

| File | Tag Type | Target | Priority |
|------|----------|--------|----------|
| history_api.dart | @MX:NOTE | API 클라이언트 공개 메서드 | P2 |
| meeting_list_provider.dart | @MX:ANCHOR | syncFromServer() (fan_in >= 3) | P1 |
| meeting_card.dart | @MX:NOTE | 삭제 제스처 핸들러 | P3 |

---

*Plan Version: 1.0.0*
*Last Updated: 2026-06-03*
