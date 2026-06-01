# SPEC-PHASE1: Quick Wins - Custom Vocabulary, Find & Replace, Clipboard Copy

## Overview
Phase 1 (Quick Wins) of the Plaud-competitive feature roadmap. Three features that deliver immediate user value with minimal risk.

## Features

### 1. Custom Vocabulary (REQ-VOCAB-001)
**Goal**: Improve STT accuracy for domain-specific terms (names, jargon, acronyms).

**Backend**:
- Add `initial_prompt` parameter to `WhisperEngine.transcribe()` and all 3 backends (mlx, faster-whisper, openai-whisper)
- New `CustomVocabulary` DB model: `id`, `name`, `words` (JSON list), `created_at`, `updated_at`
- New `/api/v1/vocabulary` CRUD endpoints (list, create, update, delete)
- Thread `initial_prompt` from upload endpoint through `transcription_task` → `engine.transcribe()`
- Vocabulary words joined by spaces form the `initial_prompt` string (Whisper convention)

**Frontend**:
- Vocabulary management screen (add/remove words, save lists)
- Vocabulary selection in recording/upload flow

**EARS**: The system SHALL accept an optional vocabulary parameter during audio upload, and when provided, SHALL pass the vocabulary terms as `initial_prompt` to the Whisper STT engine.

### 2. Find & Replace (REQ-FIND-001)
**Goal**: Search and replace text within transcript and summary views.

**Frontend only** (no backend changes):
- Search bar with text input, match count, prev/next navigation
- Highlight matching terms using `RichText`/`TextSpan`
- Replace functionality (replace current / replace all)
- Works on TranscriptTab and SummaryTab content

**EARS**: The system SHALL provide a find-and-replace interface on the transcript and summary tabs, and SHALL highlight all matching terms in real-time as the user types.

### 3. Clipboard Copy (REQ-CLIPBOARD-001)
**Goal**: One-click copy of transcript, summary, or minutes content.

**Frontend only** (no backend changes):
- Copy button on TranscriptTab (copies full transcript text)
- Copy button on SummaryTab (copies summary text + key decisions + next steps)
- Copy button on MinutesTab (copies formatted minutes)
- Visual feedback via SnackBar on successful copy

**EARS**: The system SHALL provide a copy-to-clipboard button on each content tab, and SHALL display confirmation feedback when content is copied.

## Technical Design

### Backend API

```
GET    /api/v1/vocabulary              - List all vocabularies
POST   /api/v1/vocabulary              - Create vocabulary {name, words: [...]}
PUT    /api/v1/vocabulary/{vocab_id}   - Update vocabulary {name?, words?}
DELETE /api/v1/vocabulary/{vocab_id}   - Delete vocabulary
```

### STT Engine Changes
- `WhisperEngine.transcribe(audio_path, language, initial_prompt=None)`
- `_transcribe_mlx(audio_path, language, initial_prompt=None)` → passes to `mlx_whisper.transcribe(initial_prompt=...)`
- `_transcribe_whisper(audio_path, language, initial_prompt=None)` → passes to `whisper.transcribe(initial_prompt=...)`
- `_transcribe_faster_whisper(audio_path, language, initial_prompt=None)` → passes to `faster_whisper.transcribe(initial_prompt=...)`

### Upload Endpoint Change
- `POST /api/v1/transcriptions` gains optional Form field `vocabulary_id: str | None`
- If provided, loads vocabulary words from DB and passes as `initial_prompt`

### DB Model
```python
class CustomVocabulary(Base):
    __tablename__ = "custom_vocabularies"
    id: UUID PK
    name: str(100)          # e.g. "의료 용어", "프로젝트명"
    words: JSON             # ["김인빈", "mlx-whisper", "ROS2"]
    created_at: datetime
    updated_at: datetime
```

## Acceptance Criteria
1. AC-VOCAB-001: User can create, list, update, delete vocabularies via API
2. AC-VOCAB-002: Audio upload with vocabulary_id produces more accurate transcription for included terms
3. AC-FIND-001: Search bar appears on TranscriptTab and SummaryTab
4. AC-FIND-002: Matching terms are highlighted in yellow
5. AC-FIND-003: Replace current / replace all functions work correctly
6. AC-CLIP-001: Copy button copies content to system clipboard
7. AC-CLIP-002: SnackBar confirms "클립보드에 복사되었습니다"
8. All existing 1108 backend tests continue to pass

## Out of Scope
- Per-user vocabulary ownership (Phase 2 with auth integration)
- Vocabulary sharing between users
- AI-suggested vocabulary from meeting context
