# SPEC-PHASE3: Intelligent Analytics & Mobile Experience

## Overview
Phase 3 completes Phase 2 remaining features and connects existing backend analytics infrastructure (sentiment, statistics, bookmarks) to Flutter UI. Adds collaboration UI, mobile native features, and advanced analytics.

## Existing Backend Infrastructure (No Flutter Frontend)

Backend APIs already implemented but unused by Flutter client:
- `POST/GET/DELETE /api/v1/sentiment` — Sentiment analysis
- `POST /api/v1/audio-analysis` — Audio quality analysis
- `GET /api/v1/statistics/{task_id}` — Meeting statistics
- `POST/GET/PATCH/DELETE /api/v1/bookmarks` — Bookmarks/highlights CRUD
- `POST/DELETE /meetings/{task_id}/share` — Meeting sharing (team_api.dart exists)

## Features

### 1. Phase 2 Remaining: Audio Enhancement (REQ-AUDIO-ENHANCE-001)

**Audio Speed Control**:
- Add `setSpeed(double rate)` to `AudioPlayerNotifier`
- Speed selector chip row in `AudioPlayerBar` (0.5x, 0.75x, 1.0x, 1.25x, 1.5x, 2.0x)
- Persist selected speed per session

**Transcript Sync**:
- Track `currentSegmentIndex` based on audio position + segment timestamps
- Highlight active segment in transcript tab during playback
- Tap segment → seek audio to segment start time

**Speaker Name in Transcript**:
- Use `speakerNameMapProvider` to replace "SPEAKER_00" with display names
- Tap speaker badge → dialog to assign/rename speaker profile

**EARS**: The system SHALL provide playback speed control (0.5x-2.0x), highlight transcript segments during playback, and allow users to jump to segments by tapping them.

### 2. Analytics Dashboard (REQ-ANALYTICS-001)

**Sentiment Analysis UI**:
- Trigger sentiment analysis from result screen
- Display sentiment timeline chart (positive/negative/neutral per segment)
- Overall sentiment score indicator

**Meeting Statistics UI**:
- Speaking time distribution by speaker (pie/bar chart)
- Talk ratio, silence ratio, interruption count
- Speaker engagement metrics

**Bookmarks UI**:
- Add bookmark on any transcript segment (long press → "Bookmark")
- Bookmark list tab or section in result screen
- Edit bookmark notes, color-code highlights
- Navigate from bookmark to transcript position

**EARS**: The system SHALL display sentiment analysis results as a timeline, present meeting statistics with visual charts, and allow users to bookmark transcript segments with notes.

### 3. Collaboration/Sharing UI (REQ-COLLAB-001)

**Meeting Share Dialog**:
- Share button in result screen AppBar
- Select team to share with (from team list)
- Share status indicator (which teams have access)
- Unshare option

**Bookmark Collaboration**:
- View shared bookmarks from team members
- @MX:TODO: Real-time bookmark sync (future)

**EARS**: The system SHALL allow users to share meeting results with teams and manage shared access from the result screen.

### 4. Mobile/iOS Native (REQ-MOBILE-001)

**Push Notifications**:
- Firebase Cloud Messaging (FCM) integration
- Notify on: transcription complete, summary ready, team share received
- Notification preferences screen

**Background Audio Recording**:
- Continue recording when app is backgrounded on iOS
- Audio session configuration for background mode
- Recording indicator in iOS status bar

**EARS**: The system SHALL send push notifications for pipeline completion events and continue audio recording when the app enters background on iOS.

## Technical Design

### Backend — No changes needed
All analytics, bookmarks, and sharing APIs already exist.

### Flutter New Dependencies
```yaml
fl_chart: ^0.69.0          # Charts for statistics/sentiment
firebase_core: ^3.0.0      # Push notifications
firebase_messaging: ^15.0.0 # FCM
flutter_local_notifications: ^18.0.0  # Local notification display
```

### New Flutter Files
```
client/lib/
├── services/
│   ├── sentiment_api.dart      # Sentiment analysis API client
│   ├── statistics_api.dart     # Meeting statistics API client
│   └── bookmark_api.dart       # Bookmarks CRUD API client
├── providers/
│   ├── sentiment_provider.dart # Sentiment state management
│   ├── statistics_provider.dart# Statistics state management
│   └── bookmark_provider.dart  # Bookmarks state management
├── screens/
│   └── notification_settings_screen.dart
├── widgets/
│   ├── sentiment_chart.dart    # Sentiment timeline widget
│   ├── statistics_chart.dart   # Speaking time chart widget
│   └── bookmark_list.dart      # Bookmark list widget
```

### Modified Flutter Files
```
client/lib/
├── providers/audio_player_provider.dart  # Add speed control
├── widgets/audio_player_bar.dart         # Add speed chips
├── screens/result_screen.dart            # Transcript sync, share, analytics tabs
├── widgets/speaker_segment.dart          # Tap to rename, highlight
├── pubspec.yaml                          # New dependencies
├── router/app_router.dart                # New routes
```

## Implementation Order

### Sprint 3A: Phase 2 Remaining — Audio Enhancement (1 session)
1. Audio speed control (provider + UI)
2. Transcript sync (segment highlighting during playback)
3. Speaker name display in transcript (tap to rename)

### Sprint 3B: Analytics Dashboard (1-2 sessions)
1. Sentiment API client + provider
2. Sentiment chart widget + result screen integration
3. Statistics API client + provider
4. Statistics chart widget + result screen integration
5. Bookmark API client + provider
6. Bookmark UI (add/view/navigate)

### Sprint 3C: Collaboration UI (1 session)
1. Share dialog in result screen (team selection)
2. Shared meeting indicator
3. Share/unshare management

### Sprint 3D: Mobile/iOS Native (1-2 sessions)
1. FCM setup (Firebase project, iOS entitlements)
2. Push notification handlers
3. Background recording (audio session config)
4. Notification preferences screen

## Acceptance Criteria
1. AC-AUDIO-001: Audio player supports speed control (0.5x-2.0x)
2. AC-AUDIO-002: Transcript segments highlight during playback
3. AC-AUDIO-003: Tapping a segment seeks audio to that timestamp
4. AC-AUDIO-004: Speaker display names appear in transcript
5. AC-ANALYTICS-001: Sentiment analysis results display as timeline chart
6. AC-ANALYTICS-002: Meeting statistics show speaking time distribution
7. AC-ANALYTICS-003: Users can bookmark transcript segments with notes
8. AC-COLLAB-001: Users can share meeting results with teams from result screen
9. AC-COLLAB-002: Shared meeting access can be managed (unshare)
10. AC-MOBILE-001: Push notifications sent on pipeline completion
11. AC-MOBILE-002: Audio recording continues in background on iOS
12. All existing backend tests continue to pass
13. `flutter analyze` zero issues

## Out of Scope
- Real-time collaborative editing (Phase 4)
- Voice fingerprinting/auto speaker identification (Phase 4)
- Calendar integration (Phase 4)
- Slack/Teams integration (Phase 4)
