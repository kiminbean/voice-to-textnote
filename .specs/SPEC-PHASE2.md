# SPEC-PHASE2: Smart Productivity - Upload Integration, Audio Player, Speaker Profiles, AI Q&A, Export Expansion

## Overview
Phase 2 builds on Phase 1 foundation to deliver Plaud-competitive productivity features. Five feature groups that transform the app from a transcription tool into an intelligent meeting assistant.

## Features

### 1. Vocabulary Upload Integration (REQ-UPLOAD-VOCAB-001)
**Goal**: Complete Phase 1 gap - let users select vocabulary during audio upload.

**Frontend**:
- Add vocabulary dropdown to recording/upload screen
- Fetch vocabularies from `/api/v1/vocabulary` and display as selectable list
- Pass selected `vocabulary_id` as Form field in upload request

**EARS**: The system SHALL present a vocabulary selection dropdown during audio upload, and when a vocabulary is selected, SHALL include the `vocabulary_id` in the upload request to the backend.

### 2. Audio Player + Transcript Sync (REQ-AUDIO-001)
**Goal**: In-app audio playback synchronized with transcript highlighting.

**Backend**:
- Add `GET /api/v1/meetings/{meeting_id}/audio` endpoint to serve stored audio files
- Store audio file path in meeting record (already stored during upload)

**Frontend**:
- Audio player bar at bottom of ResultScreen (persistent across tabs)
- Play/pause, seek bar, speed control (0.5x - 2.0x), time display
- Transcript sync: highlight current segment based on playback position
- Click-on-segment to jump audio to that timestamp
- Add `just_audio` package for cross-platform audio playback

**EARS**: The system SHALL provide an audio player on the result screen, and SHALL highlight the transcript segment corresponding to the current playback position in real-time.

### 3. Speaker Profiles (REQ-SPEAKER-001)
**Goal**: Name and save speaker identities across meetings.

**Backend**:
- Extend existing speaker models (already have `backend/db/speaker_models.py`)
- `SpeakerProfile` model: `id`, `name`, `voiceprint_id` (optional), `created_at`
- `SpeakerAssignment` model: links diarization speaker_id to SpeakerProfile per meeting
- API: `GET/POST/PUT/DELETE /api/v1/speaker-profiles`
- API: `POST /api/v1/meetings/{meeting_id}/speakers/assign` - assign profile to speaker_id

**Frontend**:
- Click speaker name in transcript → dialog to assign/rename
- Speaker profile management screen
- Speaker statistics: total speaking time across meetings, frequency

**EARS**: The system SHALL allow users to assign custom names to speakers identified by diarization, and SHALL persist these assignments for reuse across meetings.

### 4. AI Meeting Q&A (REQ-QA-001)
**Goal**: Ask natural language questions about meeting content.

**Backend**:
- New `GET /api/v1/meetings/{meeting_id}/ask` endpoint
- Request: `{"question": "어떤 결정이 내려졌나요?"}`
- Response: `{"answer": "...", "sources": [{"segment_id": 5, "text": "..."}]}`
- Uses Claude API with meeting transcript as context
- Conversation history support: `POST /api/v1/meetings/{meeting_id}/ask` with thread_id

**Frontend**:
- Q&A tab or floating chat panel on ResultScreen
- Chat-style interface with message bubbles
- Source citations link back to transcript segments
- Question history persistence

**EARS**: The system SHALL accept natural language questions about meeting content and return answers grounded in the meeting transcript with source citations.

### 5. Export Expansion (REQ-EXPORT-001)
**Goal**: Multiple export formats beyond PDF.

**Backend**:
- Markdown export: `GET /api/v1/meetings/{meeting_id}/export/markdown`
- DOCX export: `GET /api/v1/meetings/{meeting_id}/export/docx`
- Share link: `POST /api/v1/meetings/{meeting_id}/share` → returns shareable URL
- All formats include: transcript, summary, action items, speaker info

**Frontend**:
- Export dropdown on ResultScreen with format options (PDF, Markdown, DOCX)
- Share button generates link and copies to clipboard
- Share via email/Slack integration

**EARS**: The system SHALL provide export in PDF, Markdown, and DOCX formats, and SHALL generate shareable links for meeting content.

## Technical Design

### Backend API Additions

```
# Audio
GET  /api/v1/meetings/{meeting_id}/audio          - Stream audio file

# Speaker Profiles
GET    /api/v1/speaker-profiles                    - List profiles
POST   /api/v1/speaker-profiles                    - Create profile
PUT    /api/v1/speaker-profiles/{profile_id}       - Update profile
DELETE /api/v1/speaker-profiles/{profile_id}       - Delete profile
POST   /api/v1/meetings/{meeting_id}/speakers/assign - Assign profile to speaker

# AI Q&A
POST   /api/v1/meetings/{meeting_id}/ask           - Ask question
GET    /api/v1/meetings/{meeting_id}/ask/history    - Get Q&A history

# Export
GET    /api/v1/meetings/{meeting_id}/export/markdown - Export as Markdown
GET    /api/v1/meetings/{meeting_id}/export/docx    - Export as DOCX
POST   /api/v1/meetings/{meeting_id}/share          - Generate share link
```

### New Flutter Dependencies
- `just_audio: ^0.9.40` - Cross-platform audio player (web, macOS, iOS, Android)
- `audio_session: ^0.1.21` - Audio session management (paired with just_audio)

### DB Models

```python
class SpeakerProfile(Base):
    __tablename__ = "speaker_profiles"
    id: UUID PK
    name: str(100)          # e.g. "김인빈", "이영희"
    description: str(500)   # Optional notes
    created_at: datetime
    updated_at: datetime

class SpeakerAssignment(Base):
    __tablename__ = "speaker_assignments"
    id: UUID PK
    meeting_id: UUID FK     # -> meetings.id
    speaker_id: str(20)     # "SPEAKER_00", "SPEAKER_01" from diarization
    profile_id: UUID FK     # -> speaker_profiles.id
    assigned_at: datetime

class MeetingQA(Base):
    __tablename__ = "meeting_qa"
    id: UUID PK
    meeting_id: UUID FK
    thread_id: UUID         # Groups related Q&A
    question: str(2000)
    answer: str(5000)
    sources: JSON           # [{"segment_id": 5, "text": "..."}]
    created_at: datetime
```

## Implementation Order

### Sprint 2A: Upload Integration + Audio Player (1-2 sessions)
1. Add vocabulary dropdown to upload/recording screen
2. Audio player backend endpoint
3. Flutter audio player widget
4. Transcript sync (highlight current segment)

### Sprint 2B: Speaker Profiles (1 session)
1. Backend speaker profile models + API
2. Speaker assignment API
3. Flutter speaker naming UI in transcript
4. Speaker profile management screen

### Sprint 2C: AI Q&A (1-2 sessions)
1. Backend Q&A endpoint with Claude integration
2. Conversation history persistence
3. Flutter chat UI for Q&A
4. Source citation linking

### Sprint 2D: Export Expansion (1 session)
1. Markdown export backend
2. DOCX export backend (python-docx)
3. Share link generation
4. Flutter export format picker UI

## Acceptance Criteria
1. AC-UPLOAD-001: Vocabulary dropdown appears on upload screen
2. AC-UPLOAD-002: Selected vocabulary_id is sent with upload request
3. AC-AUDIO-001: Audio player plays meeting recording with play/pause/seek
4. AC-AUDIO-002: Current transcript segment highlights during playback
5. AC-AUDIO-003: Clicking a segment jumps audio to that timestamp
6. AC-SPEAKER-001: Users can assign custom names to speakers
7. AC-SPEAKER-002: Speaker names persist and appear in future meetings
8. AC-QA-001: Users can ask questions about meeting content
9. AC-QA-002: Answers include source citations from transcript
10. AC-EXPORT-001: Meetings can be exported as Markdown
11. AC-EXPORT-002: Meetings can be exported as DOCX
12. AC-EXPORT-003: Shareable links can be generated
13. All existing backend tests continue to pass

## Out of Scope
- Voice fingerprinting for automatic speaker identification (Phase 3)
- Real-time transcription during recording (Phase 3)
- Collaboration features (comments, shared editing) (Phase 4)
- Calendar integration (Phase 4)
