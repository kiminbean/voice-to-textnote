# Owll Benchmark PRD

**Status**: Study Pack core implemented; Cross-Meeting Q&A evidence search and synthesis exposed in search; follow-up competitive gaps remain  
**Created**: 2026-06-21  
**Owner**: Voice to TextNote  
**Scope**: Benchmark Owll AI Note Taker & Assistant and define feature upgrades that fit this project.

## 1. Research Summary

Owll positions itself as an AI note taker, recorder, and second brain across iPhone, iPad, Apple Watch, Android, and Web. Public store and product pages emphasize one-tap recording, automatic transcription, AI summaries, action items, searchable transcripts, note Q&A, sharing, multilingual transcription/translation, study aids, and meeting-platform capture.

Sources checked:

- App Store: https://apps.apple.com/us/app/owll-ai-note-taker-assistant/id6450300197
- Google Play: https://play.google.com/store/apps/details?id=com.hmd.quickrecorder
- Owll website: https://owll.ai/
- Owll AI transcription page: https://owll.ai/ai-transcription
- Owll meeting recorder blog: https://owll.ai/blog/best-meeting-recorder-app
- Owll team plan blog: https://owll.ai/blog/ai-note-taker-for-teams
- Owll transcription workflow blog: https://owll.ai/blog/best-ai-transcription-tools-how-to-turn-meetings-into-action

## 2. Current Project Baseline

Voice to TextNote already covers many core Owll-equivalent capabilities:

- Audio upload and recording pipeline
- Whisper-based STT
- Speaker diarization and speaker profiles
- Minutes generation
- AI summary and action items
- Meeting Q&A
- Search, advanced search, tags, bookmarks, vocabulary, templates
- PDF/DOCX/export and share flow
- Team workspace, meeting sharing, JWT auth
- Mobile background recording, push notifications, deep links
- Offline STT hybrid pipeline
- Sentiment and tone analysis
- Obsidian vault export
- Release-readiness validation and physical-device evidence workflow

## 3. Competitive Gap Analysis

| Owll capability | Current project status | Gap | Priority |
| --- | --- | --- | --- |
| One-tap Apple Watch recording | No Watch app surface found | New capture surface for quick voice notes | P2 |
| Ask AI across notes/files/summaries | Per-meeting Q&A exists | Cross-meeting knowledge-base Q&A is missing | P1 |
| Flashcards and AI quizzes | No flashcard/quiz model or UI found | Study pack generation from transcripts/summaries | P0 |
| Lecture/study mode | Templates exist, but no dedicated study workflow | Dedicated lecture notes + review artifacts | P0 |
| YouTube summary | No YouTube URL ingestion found | URL import and transcript/summarize pipeline | P1 |
| OCR for PDFs/images | Export exists, OCR import not found | Document/image import into searchable notes | P2 |
| 100+ language transcription/translation | Backend translation API implemented for persisted minutes/summaries; Korean default and i18n UI exist | Flutter translation UI, export/search integration, and broader multilingual transcript workflow remain | P1 |
| Online meeting capture for Zoom/Meet/Teams | Roadmap mentions Slack/Teams, no bot/import surface found | Meeting-platform import/integration | P2 |
| Contact manager for sales notes | Team/auth exist, no CRM/contact model found | Sales follow-up/contact workflows | P3 |
| SOAP/healthcare note mode | Generic templates exist | Domain-specific summary template | P3 |
| Private cloud per team member | Team sharing exists | Explicit private-by-default note ownership and sharing policy UX | P1 |
| Summary modes 10+ | Templates/summaries exist | User-selectable summary modes should be productized | P1 |

## 4. Product Direction

Do not copy Owll feature-for-feature. Improve the project by leaning into strengths Owll does not foreground: local/privacy-first processing, offline STT, richer meeting analytics, Obsidian export, and strict release evidence.

The first implementation should be a Study Pack feature because it is high-impact, fits existing backend summary/Q&A infrastructure, avoids new native platform risk, and creates a visible competitive upgrade for lectures, interviews, sermons, and research recordings.

## 5. PRD: Study Pack Generation

**Implementation status (2026-06-21)**: Backend schema/service/API, mode-specific caching, Flutter API/provider/model, Result screen Study tab, copy/regenerate controls, source references, loading/empty/error states, mode selection, Obsidian study sections, and summary search indexing for Study Pack text are implemented.

### 5.1 Problem

Users can currently transcribe, summarize, search, and export meetings, but learners and researchers still need to manually convert long transcripts into revision material. Owll markets flashcards, quizzes, lecture notes, and study guides as a key advantage. Voice to TextNote should provide a privacy-first version that turns existing meeting artifacts into structured study material.

### 5.2 Goals

- Generate study packs from completed transcription/minutes/summary results.
- Support lecture notes, flashcards, quiz questions, and key concepts.
- Preserve citations back to transcript timestamps or speaker segments where possible.
- Provide an API and Flutter UI that fit existing result and analytics screens.
- Keep generated content exportable and searchable.

### 5.3 Non-Goals

- No new external dependency in the first iteration.
- No YouTube download, OCR, Apple Watch, or meeting bot in the first iteration.
- No medical/legal regulated workflow claims.
- No automatic sharing outside existing team/meeting-share controls.

### 5.4 Users

- Students reviewing lectures.
- Researchers reviewing interviews.
- Product/design teams reviewing user research calls.
- Managers reviewing long meetings and extracting learning points.
- Individuals using voice notes as a personal knowledge base.

### 5.5 User Stories

- As a student, I can convert a lecture transcript into flashcards so I can review faster.
- As a researcher, I can generate quiz questions from an interview so I can validate topic comprehension.
- As a meeting owner, I can view key concepts and timestamp references so I can jump back to source context.
- As a team member, I can share a study pack using the existing meeting share permissions.
- As an offline-first user, I can generate a study pack from locally produced transcript data once a summary provider is available.

### 5.6 Functional Requirements

#### Backend

- Add a study-pack schema with:
  - `task_id`
  - `mode`: `lecture`, `meeting`, `interview`, `sermon`, `general`
  - `language`
  - `key_concepts`
  - `flashcards`
  - `quiz_questions`
  - `study_notes`
  - `source_refs`
  - `created_at`
- Add generation service that consumes existing transcript/minutes/summary payloads.
- Use existing OpenAI client/config patterns where AI generation is already used.
- Cache or persist generated study packs consistently with current result storage conventions.
- Expose endpoints:
  - `POST /api/v1/minutes/{task_id}/study-pack`
  - `GET /api/v1/minutes/{task_id}/study-pack?mode={mode}`
- Return deterministic validation errors when source transcript/minutes are unavailable.
- Include prompt-level guardrails to avoid inventing facts not present in the transcript.

#### Flutter

- Add a Study tab or section to the result screen.
- Let users select study mode before generation.
- Display:
  - Key concepts
  - Flashcards
  - Quiz questions with hidden answers
  - Study notes
  - Source timestamp/speaker references when available
- Add loading, empty, error, and retry states.
- Reuse existing theme, cards, tabs, and provider patterns.

#### Export/Search

- Include study pack content in existing export flow where practical. *(Implemented for Obsidian manual/auto export.)*
- Make generated key concepts searchable or at least visible from the meeting result. *(Implemented for summary search indexing when Study Pack content is present in the summary payload.)*
- Preserve Obsidian export compatibility by adding a study section to exported markdown later. *(Implemented.)*

### 5.7 Acceptance Criteria

- Given a completed meeting with transcript text, when the user generates a study pack, then the response contains at least 3 key concepts, 3 flashcards, 3 quiz questions, and a study-note summary.
- Given missing source content, the API returns a clear 404 or 422 without creating empty study material.
- Given a generated flashcard, the answer must be grounded in transcript or summary content.
- Given a quiz question, it includes question, answer, difficulty, and optional source reference.
- Given a Flutter result page, users can generate and review study material without leaving the meeting context.
- Backend tests cover success, missing source, malformed AI response, and caching/persistence behavior.
- Flutter tests cover provider state and basic rendering of generated flashcards/quizzes.

### 5.8 Metrics

- Study pack generation success rate
- Median generation latency
- Percent of generated items with source refs
- User actions: copy/share/export flashcard or quiz
- Regeneration count per meeting

## 6. Follow-Up PRDs

### P1: Cross-Meeting Knowledge Q&A

Extend current per-meeting Q&A into cross-meeting search + answer synthesis. Use existing search index and permissions. This competes with Owll's “Ask AI across your notes” while preserving private/team boundaries.

**Implementation status (2026-06-21)**: First backend and Flutter slice implemented. `POST /api/v1/qa/ask-across` normalizes the user's natural-language question into FTS keywords, searches existing minutes/summary/study-pack search index rows across meetings, and returns a source-grounded synthesized answer with source task IDs, snippets, task types, and timestamps. The Flutter search screen now shows those sources in an "AI 근거 검색" panel above regular search results. If answer synthesis fails or returns empty content, the backend falls back to an extractive source summary instead of fabricating unsupported facts.

#### Problem

Per-meeting Q&A only works after the user already knows which recording contains the answer. Owll markets a broader “ask across notes/files/summaries” workflow, so Voice to TextNote should let users ask a question first and discover the relevant meetings second.

#### Goals

- Search across indexed meeting minutes, summaries, and Study Pack terms from one natural-language question.
- Return source-backed results that can be opened in the existing meeting/result UI later.
- Reuse existing SQLite FTS5 search infrastructure and release-readiness discipline.
- Keep generated answers grounded in retrieved snippets and preserve source IDs in every response.

#### Functional Requirements

- Add a cross-meeting Q&A request schema with `question` and bounded `limit`.
- Add a response schema with `answer`, `sources`, normalized `query`, and `total`.
- Reuse the existing `search_index` FTS5 table.
- Normalize common Korean particles/suffixes so questions like “API 개발에서 결정된 내용은?” search for meaningful terms such as “API 개발 결정”.
- Return a clear 404 when no relevant meeting context is found.
- Do not call external LLMs in the first slice; use retrieved snippets as the only answer basis.

#### Acceptance Criteria

- Given indexed minutes and summary rows, when the user asks a cross-meeting question, then the API returns relevant source task IDs and non-empty snippets.
- Given a question with no searchable terms, the service rejects it with a deterministic validation error.
- Given no matching source rows, the API returns 404 without fabricating an answer.
- Route registry invariance is updated so the new endpoint remains covered by API surface tests.
- Given a search query in Flutter, the search screen displays available cross-meeting sources above regular results.

### P1: Multilingual Transcript Translation

Add transcript and summary translation workflows. The current app has Korean/English UI localization and a configurable Whisper language, but not a productized transcript translation flow.

**Implementation status (2026-06-21)**: First backend slice implemented. `POST /api/v1/minutes/{task_id}/translation` translates persisted minutes or summary text into a target language, preserves speaker/timestamp/markdown structure in the prompt, stores results under `TaskResult.result_data["translations"]`, and `GET /api/v1/minutes/{task_id}/translation?target_language={language}` returns cached translations. Remaining work: Flutter result-screen UI, export/search inclusion, and broader multilingual transcript UX.

### P1: Summary Modes

Productize reusable summary modes such as executive brief, lecture notes, sales follow-up, sermon notes, research interview, action-only, and decision log.

### P2: YouTube and External Media Import

Add URL import and transcript generation for user-provided external media. This requires careful legal, content-source, and rate-limit handling.

### P2: OCR Import

Import PDFs/images into searchable note context. This is useful for slides, handouts, receipts, whiteboards, and screenshots.

### P2: Apple Watch Quick Capture

Create a minimal Apple Watch companion for one-tap recording or recording trigger. This is a native-platform project and should wait until core mobile release evidence is complete.

### P3: Domain Packs

Add optional sales/contact follow-up and SOAP-style healthcare templates as configurable modes, without making regulated claims.

## 7. Implementation Plan

1. Backend RED tests for study-pack schema and API.
2. Backend service implementation using existing summary/OpenAI patterns.
3. Persistence/cache integration with current result storage.
4. Flutter provider/API client/model additions.
5. Result screen Study tab UI.
6. Export/Obsidian follow-up once core generation is stable.
7. Full verification: targeted backend tests, Flutter tests/analyze, release readiness.

## 8. Risks

- AI hallucination: mitigate with source-grounded prompts and schema validation.
- Cost/latency: use explicit generation action, not automatic background generation in v1.
- Privacy: do not share generated study packs outside existing meeting/team permissions.
- UX clutter: keep Study Pack inside result context rather than adding a new top-level destination initially.
- Scope creep: defer YouTube/OCR/Watch until Study Pack is shipped and verified.
