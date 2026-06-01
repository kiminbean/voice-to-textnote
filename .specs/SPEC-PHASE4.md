# SPEC-PHASE4: Integrations, Collaboration & Voice Intelligence

## Overview
Phase 4 adds external integrations, real-time collaboration, and advanced voice intelligence. Builds on existing JWT auth, team system, webhook infrastructure, and SSE streaming from Phase 1-3.

**Prerequisite**: Phase 3 complete (25/25 SPECs done).

## Existing Infrastructure (Foundation for Phase 4)

### Backend
- JWT auth with refresh token rotation (`backend/app/middleware/auth.py`, `backend/app/api/v1/auth.py`)
- Guest session support (`is_guest`, `guest_session_id` fields)
- Team CRUD + member management (`backend/app/api/v1/teams.py`, `backend/db/auth_models.py`)
- Meeting sharing via `MeetingOwnership` model (task_id + owner_id + team_id)
- Webhook endpoint management (`backend/app/api/v1/webhooks.py`) - CRUD + ping, per-user
- SSE streaming (`backend/app/api/v1/stream.py`) - Redis pub/sub based
- Speaker diarization (`pyannote.audio 3.1`) - produces speaker labels but not persistent identities
- Redis pub/sub for task events (`backend/events/subscriber.py`)
- `WebhookService` with URL validation and event dispatch

### Frontend
- Riverpod state management (13 providers)
- go_router with auth guard + guest mode
- SSE service (`client/lib/services/sse_service.dart`)
- 22 API service files including team, auth, bookmark, sentiment APIs
- Result screen with 7 tabs (~2763 lines)

### Database
- `User` model (email/password, display_name, is_active)
- `Team`, `TeamMember` (admin/member/viewer roles)
- `MeetingOwnership` (task_id + owner_id + team_id, unique constraint)
- `RefreshToken` (JWT rotation with hash storage)
- SQLite (dev) / PostgreSQL (prod) with SQLAlchemy 2.0

### Missing (Must Build)
- No OAuth/social login fields on User model
- No WebSocket infrastructure (SSE only)
- No voice fingerprint model or service
- No calendar integration models or endpoints
- No Slack/Teams API clients
- No real-time collaboration (CRDT/OT) engine
- No comment/annotation system

---

## Features

### 1. OAuth Social Login (REQ-OAUTH-001)

**Backend Changes**:
- Add `provider` (String: "email", "google", "apple") and `provider_id` (String, nullable) to User model
- Add `avatar_url` (String, nullable) for profile pictures
- `POST /api/v1/auth/google` - Google OAuth2 token verification (google-auth library)
- `POST /api/v1/auth/apple` - Apple ID token verification (pyjwt + apple public keys)
- Link/unlink social accounts: `POST /api/v1/auth/link/{provider}`, `DELETE /api/v1/auth/link/{provider}`
- Auto-create User on first social login (no password required)

**Frontend Changes**:
- Add `google_sign_in` and `sign_in_with_apple` packages to pubspec.yaml
- Social login buttons on LoginScreen
- New `AuthProvider` methods: `loginWithGoogle()`, `loginWithApple()`
- Account linking UI in profile/settings screen

**EARS**: The system SHALL support Google and Apple social login, auto-create accounts on first login, and allow linking social accounts to existing email-based accounts.

### 2. Real-time Collaborative Editing (REQ-COLLAB-RT-001)

**Backend**:
- WebSocket endpoint: `WS /api/v1/ws/meetings/{task_id}/collab`
- Connection requires JWT auth (query param or first message)
- Broadcast edit operations to all connected users in same meeting
- User presence tracking (join/leave events)
- Operation transform for text edits (simplified OT - not full CRDT)
- Edit conflict resolution: last-write-wins at segment level
- Cursor position sharing (optional, Sprint 4C)

**Database**:
- New `CollabSession` model: user_id, task_id, joined_at, last_active_at
- New `EditOperation` model: task_id, user_id, operation_type (insert/delete/replace), position, content, version, created_at

**Frontend**:
- Add `web_socket_channel` package
- New `CollabProvider` (Riverpod): manages WebSocket connection, local/remote edits
- User presence indicators (avatar bubbles) on result screen transcript tab
- Edit operations sent as JSON diffs (operational transformation)
- Conflict indicators when concurrent edits detected

**EARS**: The system SHALL allow multiple users to edit meeting minutes simultaneously via WebSocket, show user presence indicators, and resolve edit conflicts with operational transformation.

### 3. Comments & Annotations (REQ-COMMENT-001)

**Backend**:
- `POST /api/v1/meetings/{task_id}/comments` - Add comment on transcript segment
- `GET /api/v1/meetings/{task_id}/comments` - List comments (paginated)
- `PATCH /api/v1/comments/{id}` - Edit comment
- `DELETE /api/v1/comments/{id}` - Delete comment
- `POST /api/v1/comments/{id}/replies` - Reply to comment
- Comments linked to transcript segment index + optional timestamp range

**Database**:
- New `Comment` model: id, task_id, user_id, segment_index, timestamp_start, timestamp_end, content, parent_id (for replies), created_at, updated_at

**Frontend**:
- Comment icon on each transcript segment (tap to add/view)
- Comment sidebar panel on result screen
- Reply threading (1 level deep)
- @mention team members (autocomplete from team member list)
- Real-time comment updates via collab WebSocket

**EARS**: The system SHALL allow users to add threaded comments on transcript segments, reply to comments, and see real-time comment updates from collaborators.

### 4. Voice Fingerprinting (REQ-VOICEPRINT-001)

**Backend**:
- New `VoicePrintService`: extract speaker embeddings using speechbrain or resemblyzer
- `POST /api/v1/speakers/enroll` - Upload audio sample + speaker name to create voice print
- `POST /api/v1/speakers/identify` - Run identification against enrolled voice prints
- `GET /api/v1/speakers/prints` - List enrolled voice prints
- `DELETE /api/v1/speakers/prints/{id}` - Delete voice print
- Integrate with existing diarization pipeline: after diarization, auto-identify known speakers
- Voice embeddings stored as BLOB (numpy array, ~512 floats = 2KB per print)

**Database**:
- New `VoicePrint` model: id, user_id, name, embedding (LargeBinary), sample_duration, created_at
- Add `voice_print_id` (nullable FK) to diarization result segments

**Privacy Constraint**: Voice embeddings stored locally only. No cloud upload. Embeddings are reversible (can reconstruct voice characteristics) - document this in privacy policy.

**Frontend**:
- "Enroll Speaker" flow: select speaker from diarization result → record/upload voice sample → save
- Speaker profile screen enhancement: show enrolled voice prints
- Auto-matching indicator: "SPEAKER_00 matched to 김민수 (92%)"
- Manual override: user can accept/reject auto-matching

**EARS**: The system SHALL allow users to enroll voice prints, automatically identify speakers during diarization, and allow manual correction of speaker matches.

### 5. Google Calendar Integration (REQ-CALENDAR-001)

**Backend**:
- `POST /api/v1/integrations/calendar/connect` - OAuth2 flow initiation (Google Calendar)
- `GET /api/v1/integrations/calendar/callback` - OAuth2 callback
- `GET /api/v1/integrations/calendar/events` - List upcoming calendar events
- `POST /api/v1/integrations/calendar/link` - Link meeting recording to calendar event
- `GET /api/v1/integrations/calendar/status` - Check connection status
- `DELETE /api/v1/integrations/calendar/disconnect` - Revoke OAuth tokens

**Database**:
- New `CalendarIntegration` model: id, user_id, provider ("google"), access_token (encrypted), refresh_token (encrypted), token_expires_at, calendar_id, created_at
- New `MeetingCalendarLink` model: id, task_id, calendar_event_id, calendar_integration_id, created_at

**Frontend**:
- Settings screen: "Connect Google Calendar" button
- Calendar events list: upcoming meetings with "Record" button
- Auto-fill meeting title from calendar event when starting recording
- Link existing recording to calendar event

**EARS**: The system SHALL connect to Google Calendar via OAuth2, display upcoming events, and allow linking recordings to calendar events.

### 6. Slack Integration (REQ-SLACK-001)

**Backend**:
- `POST /api/v1/integrations/slack/connect` - Slack OAuth2 flow
- `GET /api/v1/integrations/slack/callback` - OAuth2 callback
- `POST /api/v1/integrations/slack/share` - Share meeting summary to Slack channel
- `GET /api/v1/integrations/slack/channels` - List available Slack channels
- `GET /api/v1/integrations/slack/status` - Connection status
- `DELETE /api/v1/integrations/slack/disconnect` - Disconnect

Leverage existing `WebhookService` for Slack webhook URL registration.

**Database**:
- New `SlackIntegration` model: id, user_id, team_id (Slack workspace), access_token (encrypted), bot_user_id, created_at
- New `SlackChannel` model: id, slack_integration_id, channel_id, channel_name, is_default

**Frontend**:
- Settings screen: "Connect Slack" button
- Channel selector when sharing meeting results
- "Share to Slack" button on result screen (alongside existing share)
- Slack notification preferences: auto-share on completion

**EARS**: The system SHALL connect to Slack workspaces, list channels, and share meeting summaries with formatted messages.

---

## Technical Design

### New Backend Dependencies
```
# requirements.txt additions
google-auth >= 2.28.0          # Google OAuth2 verification
google-auth-oauthlib >= 1.2.0  # Google Calendar OAuth2 flow
google-api-python-client >= 2.120.0  # Google Calendar API
speechbrain >= 1.0.0           # Speaker embedding extraction (voice fingerprinting)
websockets >= 12.0             # WebSocket server for real-time collab
cryptography >= 42.0.0         # Token encryption for integrations
```

### New Flutter Dependencies
```yaml
# pubspec.yaml additions
google_sign_in: ^6.2.0           # Google OAuth
sign_in_with_apple: ^6.1.0       # Apple Sign-In
web_socket_channel: ^3.0.0       # WebSocket client
crypto: ^3.0.3                   # Encryption helpers
```

### New Backend Files
```
backend/
├── app/api/v1/
│   ├── collab.py              # WebSocket collaborative editing
│   ├── comments.py            # Comment CRUD endpoints
│   ├── voiceprint.py          # Voice fingerprint enrollment/identification
│   └── integrations/
│       ├── __init__.py
│       ├── calendar.py        # Google Calendar OAuth + events
│       └── slack.py           # Slack OAuth + share
├── db/
│   ├── collab_models.py       # CollabSession, EditOperation, Comment models
│   ├── voiceprint_models.py   # VoicePrint model
│   └── integration_models.py  # CalendarIntegration, SlackIntegration models
├── services/
│   ├── collab_service.py      # OT engine, presence management
│   ├── voiceprint_service.py  # Embedding extraction + matching
│   ├── calendar_service.py    # Google Calendar API wrapper
│   └── slack_service.py       # Slack API wrapper
└── schemas/
    ├── collab.py              # WebSocket message schemas
    ├── comment.py             # Comment request/response schemas
    ├── voiceprint.py          # Voiceprint schemas
    └── integration.py         # Calendar/Slack schemas
```

### New Flutter Files
```
client/lib/
├── providers/
│   ├── collab_provider.dart   # WebSocket connection + edit sync
│   ├── comment_provider.dart  # Comment state management
│   ├── voiceprint_provider.dart # Voice print management
│   └── integration_provider.dart # Calendar/Slack state
├── services/
│   ├── collab_api.dart        # WebSocket client for collab
│   ├── comment_api.dart       # Comment REST API client
│   ├── voiceprint_api.dart    # Voiceprint REST API client
│   ├── calendar_api.dart      # Calendar REST API client
│   └── slack_api.dart         # Slack REST API client
├── screens/
│   ├── integration_settings_screen.dart  # Calendar/Slack settings
│   └── speaker_enroll_screen.dart        # Voice print enrollment
└── widgets/
    ├── comment_panel.dart     # Comment sidebar
    ├── presence_indicator.dart # User avatars
    └── calendar_event_card.dart # Calendar event widget
```

### Modified Files
```
# Backend
backend/db/auth_models.py               # Add provider, provider_id, avatar_url to User
backend/app/config.py                   # Add Google/Apple/Slack OAuth config
backend/app/middleware/auth.py          # Support OAuth token verification
backend/app/api/v1/auth.py             # Social login endpoints
backend/app/api/v1/speakers.py         # Voice print matching integration
backend/app/dependencies.py            # WebSocket auth dependency

# Frontend
client/lib/providers/auth_provider.dart  # Social login methods
client/lib/services/auth_api.dart        # Social login API calls
client/lib/screens/login_screen.dart     # Social login buttons
client/lib/screens/result_screen.dart    # Comments, presence, collab editing
client/lib/screens/speaker_profile_screen.dart # Voice print enrollment
client/lib/router/app_router.dart        # New routes (integration settings)
client/pubspec.yaml                      # New dependencies
```

---

## Implementation Order

### Sprint 4A: OAuth Social Login (1-2 sessions)
1. Backend: Extend User model with provider/provider_id/avatar_url
2. Backend: Google OAuth2 token verification endpoint
3. Backend: Apple ID token verification endpoint
4. Backend: Account linking/unlinking endpoints
5. Frontend: `google_sign_in` + `sign_in_with_apple` integration
6. Frontend: Social login buttons on LoginScreen
7. Frontend: AuthProvider social login methods
8. Tests: OAuth flow unit tests (mock token verification)

### Sprint 4B: Real-time Collaboration (2-3 sessions)
1. Backend: WebSocket endpoint with JWT auth
2. Backend: `CollabSession` + `EditOperation` models
3. Backend: Simplified OT engine (segment-level last-write-wins)
4. Backend: User presence tracking via Redis
5. Frontend: `web_socket_channel` connection management
6. Frontend: `CollabProvider` with local/remote edit sync
7. Frontend: User presence indicators on result screen
8. Tests: WebSocket connection + edit conflict scenarios

### Sprint 4C: Comments & Voice Fingerprinting (2 sessions)
1. Backend: `Comment` model + CRUD endpoints
2. Backend: `VoicePrint` model + embedding service
3. Backend: Voice print enrollment + identification endpoints
4. Backend: Integrate voice prints with diarization pipeline
5. Frontend: Comment panel on result screen
6. Frontend: Voice print enrollment flow
7. Frontend: Auto-matching display + manual override
8. Tests: Comment CRUD, voice print enrollment/identification

### Sprint 4D: Calendar & Slack Integration (2 sessions)
1. Backend: `CalendarIntegration` model + Google OAuth2 flow
2. Backend: Google Calendar API wrapper (events list, link meeting)
3. Backend: `SlackIntegration` model + Slack OAuth2 flow
4. Backend: Slack share endpoint (formatted message)
5. Frontend: Integration settings screen
6. Frontend: Calendar event list + "Record" shortcut
7. Frontend: "Share to Slack" on result screen
8. Tests: OAuth flows (mock), API wrappers

---

## Acceptance Criteria

1. AC-OAUTH-001: Users can sign in with Google account (auto-create on first login)
2. AC-OAUTH-002: Users can sign in with Apple ID (auto-create on first login)
3. AC-OAUTH-003: Existing users can link/unlink social accounts
4. AC-COLLAB-RT-001: Multiple users can edit meeting minutes simultaneously
5. AC-COLLAB-RT-002: User presence (avatars) shown during collaborative editing
6. AC-COLLAB-RT-003: Edit conflicts resolved with operational transformation
7. AC-COMMENT-001: Users can add comments on transcript segments
8. AC-COMMENT-002: Users can reply to comments (1-level threading)
9. AC-COMMENT-004: New comments appear in real-time for connected users
10. AC-VOICEPRINT-001: Users can enroll voice prints with audio samples
11. AC-VOICEPRINT-002: Diarization auto-identifies enrolled speakers
12. AC-VOICEPRINT-003: Users can accept/reject auto-matched speakers
13. AC-CALENDAR-001: Users can connect Google Calendar via OAuth2
14. AC-CALENDAR-002: Upcoming calendar events displayed in app
15. AC-CALENDAR-003: Recordings can be linked to calendar events
16. AC-SLACK-001: Users can connect Slack workspace via OAuth2
17. AC-SLACK-002: Meeting summaries can be shared to Slack channels
18. All existing tests continue to pass
19. `flutter analyze` zero issues
20. New code coverage >= 80%

---

## Privacy & Security Considerations

### Voice Fingerprints
- Voice embeddings stored locally only (no cloud)
- Embeddings can reconstruct voice characteristics - must be documented
- User can delete voice prints at any time
- Embeddings tied to user account, not shared across teams

### OAuth Tokens
- Access tokens encrypted at rest (AES-256 via cryptography library)
- Refresh tokens encrypted at rest
- Tokens stored in database, not Redis (persistence required)
- Revoke tokens on disconnect
- Token rotation on refresh

### WebSocket Security
- JWT required for WebSocket connection (query param on connect)
- Meeting access verified before allowing collab session
- Rate limiting on edit operations (prevent spam)
- Max 10 concurrent users per meeting collab session

### Data Retention
- Comments: follow meeting retention policy (30 days default)
- Edit operations: retained for conflict resolution (7 days), then purged
- Voice prints: retained until user deletes or account deletion
- OAuth tokens: retained until disconnect or account deletion

---

## Out of Scope (Phase 5)
- Microsoft Teams integration (requires Azure AD + Bot Framework)
- Full CRDT engine (Yjs/Automerge) for complex concurrent editing
- Audio/video calls within the app
- Mobile push notification for comments (depends on FCM from Phase 3D)
- AI-powered comment summarization
- Calendar event auto-scheduling based on meeting outcomes
- Voice fingerprint sharing across organizations

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Google/Apple OAuth policy changes | Medium | Pin library versions, monitor policy updates |
| WebSocket memory usage under load | High | Limit concurrent connections per meeting (10), implement heartbeat cleanup |
| Voice print accuracy < 80% | Medium | Fall back to manual diarization labels, show confidence score |
| speechbrain + mlx conflict on Apple Silicon | High | Test MPS compatibility first; use CPU fallback for embedding extraction |
| Slack API rate limits | Low | Queue share requests, respect retry-after headers |
| Edit conflict frequency in small teams | Low | Segment-level locking, visual conflict indicators |
| OAuth token leakage | High | Encrypt at rest, use HTTPS only, short-lived access tokens |

---

## Configuration Additions

```python
# backend/app/config.py additions

# Google OAuth
google_client_id: str = ""
google_client_secret: str = ""
google_calendar_scopes: list[str] = Field(
    default_factory=lambda: ["https://www.googleapis.com/auth/calendar.readonly"]
)

# Apple Sign-In
apple_team_id: str = ""
apple_client_id: str = ""
apple_key_id: str = ""

# Slack Integration
slack_client_id: str = ""
slack_client_secret: str = ""
slack_signing_secret: str = ""

# Voice Fingerprinting
voiceprint_model: str = "speechbrain/spkrec-ecapa-voxceleb"
voiceprint_similarity_threshold: float = 0.65
voiceprint_max_enrollment_samples: int = 5

# Real-time Collaboration
collab_max_users_per_meeting: int = 10
collab_heartbeat_interval_seconds: int = 30
collab_edit_buffer_ms: int = 100  # Debounce local edits
collab_operation_retention_days: int = 7

# Integration token encryption
integration_encryption_key: str = ""  # AES-256 key for OAuth token encryption
```
