# Owll Benchmark PRD

**Status**: Study Pack core implemented; Cross-Meeting Q&A evidence search and synthesis exposed in search; sales follow-up briefs are searchable and listable; 2026-06-30 benchmark refreshed; Promise Radar v2 implemented
**Created**: 2026-06-21  
**Last verified**: 2026-06-30
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

2026-06-30 additional benchmark sources checked:

- Otter AI Meeting Assistant: https://otter.ai/features/ai-meeting-assistant
- Fireflies AI meeting assistant: https://fireflies.ai/
- Notta features: https://www.notta.ai/en/features
- Granola AI notes: https://www.granola.ai/
- PLAUD AI voice recorder/note products: https://www.plaud.ai/
- NAVER CLOVA Note: https://clovanote.naver.com/

2026-06-30 competitive conclusion:

- The competitive field clusters around transcription, speaker labels, summaries, action items, meeting search/chat, translation, templates, collaboration, and integrations.
- Those features are necessary but no longer defensible as a unique reason to choose this app.
- The most defensible direction is a compounding private memory feature: something that becomes more valuable only after this user's meetings, corrected speaker names, and private history accumulate.
- Selected killer feature: **Promise Radar**. It compares the current meeting against prior meetings and surfaces repeated promises, stale promises that disappeared from the current meeting, possible decision drift, and concrete follow-up questions.
- Why it is hard to copy: it depends on long-term private meeting history, ownership boundaries, speaker/action naming hygiene, and repeated local usage. A competitor can copy the screen, but not the user's accumulated promise ledger.

2026-06-22 freshness notes:

- App Store listing shows Owll 3.16.0, 4.8 rating from 2.6K ratings, and iPhone/iPad/Apple Watch support.
- App Store positioning now explicitly includes AI Contact Manager for Sales & Client Notes, faith/sermon notes, smart folders, note sharing, Ask Owll AI, 100+ languages, YouTube import, OCR, flashcards, lecture notes, and AI quizzes.
- Google Play listing confirms Android positioning as an AI note taker and recorder, with 4.2 star rating, 354 reviews, 100K+ downloads, Everyone content rating, in-app purchases, and Jun 11, 2026 update date.
- Google Play copy explicitly mentions clear transcripts, summaries, action items, flashcards, searchable notes, supported online meeting workflows, and Ask AI across notes. Its Data safety section says the app may share messages, app activity, and other data types with third parties. This reinforces this project's privacy-first differentiation.
- Owll website still presents Zoom, Microsoft Teams, Google Meet, phone recordings, and YouTube as core inputs, plus email/Slack sharing, flashcards, summaries, encrypted cloud access, and instant translation.
- Owll Team Plan blog published Jun 17, 2026 says each seat gets 900 minutes per month, personal private cloud, 100+ languages, unlimited AI notes/chat, unlimited large uploads, one-click YouTube summary, 10+ summary modes, centralized billing, and Web/iOS/Android access.
- Source discrepancy to monitor: Owll website marketing says 50+ transcription languages, while App Store and Team Plan copy say 100+ languages.

## 2. Current Project Baseline

Voice to TextNote already covers many core Owll-equivalent capabilities:

- Audio upload and recording pipeline
- Whisper-based STT
- Speaker diarization and speaker profiles
- Minutes generation
- AI summary and action items
- Meeting Q&A
- Search, advanced search, tags, bookmarks, vocabulary, templates
- PDF/DOCX/image import, export, and share flow
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
| YouTube summary | URL/transcript import API, Flutter API client, Home URL/Transcript entry point, clipboard paste ingestion, and Android native text/URL share-sheet prefill implemented for user-provided external text | iOS share extension and compliant transcript fetching remain | P1 |
| OCR for PDFs/images | PDF/DOCX/image document import API, Flutter Home entry point, Android native share-sheet file/image ingestion, and iOS Open In file/image ingestion implemented for searchable note context, with optional image OCR runtime support | Full iOS Share Extension sheet UI remains | P2 |
| 100+ language transcription/translation | Backend translation API, Flutter result-screen translation tab, search indexing, and Obsidian export inclusion implemented for persisted minutes/summaries; Korean default and i18n UI exist | Broader multilingual transcript workflow remains | P1 |
| Online meeting capture for Zoom/Meet/Teams | Flutter Home can create Zoom/Meet/Teams meeting-link cards, open/copy them, add calendar templates, and turn shared Zoom/Meet/Teams URLs into pending online meeting cards instead of transcript imports | Actual consent-aware meeting bot/capture integration remains | P2 |
| Contact manager for sales notes | Sales follow-up summary mode, Sales Contact Brief API, Result-screen tab, searchable/cross-meeting discoverable sales brief artifacts, backend customer list API, Flutter lifecycle filters, business-card OCR intake, native camera capture, copyable contact-field confirmation, editable CRM status/notes, and CRM CSV export/share implemented | External CRM OAuth/API sync remains | P3 |
| SOAP/healthcare note mode | SOAP smart-summary mode implemented with non-diagnostic disclaimer | Domain tuning/validation and regulated clinical workflows remain out of scope | P3 |
| Private cloud per team member | Team sharing exists; history sync, meeting cards, result hero team names, team sharing dialog policy labels, and authenticated new import flows now apply team-default sharing policies while preserving private fallback | Broader capture surfaces can reuse the same policy hook | P1 |
| Summary modes 10+ | Backend smart-summary modes and Flutter result-screen mode generation implemented | Mode tuning and persisted history UX can be improved | P1 |

## 4. Product Direction

Do not copy Owll feature-for-feature. Improve the project by leaning into strengths Owll does not foreground: local/privacy-first processing, offline STT, richer meeting analytics, Obsidian export, and strict release evidence.

The first implementation should be a Study Pack feature because it is high-impact, fits existing backend summary/Q&A infrastructure, avoids new native platform risk, and creates a visible competitive upgrade for lectures, interviews, sermons, and research recordings.

2026-06-30 update: Study Pack, Cross-Meeting Q&A, translation, sales briefs, smart summary modes, and analytics are now implemented. The next differentiator is not another output format; it is continuity across meetings. Promise Radar is now the primary "must use Voice to TextNote" wedge for teams and individuals who lose decisions and follow-ups across recurring meetings.

## 4.1 Killer Feature: Promise Radar

**Implementation status (2026-06-30)**: Backend schema/service/API, route registration, Flutter API/model/provider, Result-screen `약속 레이더` tab, and focused unit/model tests are implemented. v2 adds promise chains, owner-level risk, high-risk counts, and recurring promise follow-up questions.

### Problem

Meeting assistant apps summarize what happened in one meeting, but users often lose what changed between meetings: who promised what last time, whether the promise was repeated or ignored, and whether a decision silently drifted. This is the point where summaries fail as a workflow.

### Product Bet

Voice to TextNote should become the app that remembers meeting obligations over time, not just the app that writes cleaner notes.

### UX

- A new `약속 레이더` tab appears in the meeting result screen.
- The tab shows:
  - risk score and headline
  - owner-level promise risk
  - promise chains across meetings
  - follow-up questions for the next meeting
  - stale promises from previous meetings
  - repeated/carried-over promises
  - possible decision changes
  - current meeting promises

### Backend Contract

- Endpoint: `GET /api/v1/promise-radar/{summary_task_id}?limit=30`
- Source data: persisted `TaskResult` summary rows using `action_items`, `key_decisions`, and `next_steps`.
- Access model: current task access is verified; previous meetings are filtered by current user ownership or guest session where available.
- Fallback principle: the first slice is deterministic and does not require a successful LLM call.
- v2 response additions:
  - `promise_chains`: grouped promise history with first/last seen timestamps, age, occurrence count, status, and risk level.
  - `owner_risks`: per-owner open/stale/recurring promise counts and risk score.
  - `high_risk_count`: number of high-risk chains/owners needing attention.

### Acceptance Criteria

- Given a current summary with action items, the tab lists current promises.
- Given a previous similar action item, the API returns it as a carried-over promise.
- Given a previous action item absent from the current meeting, the API returns it as stale and creates a follow-up question.
- Given related but changed decisions, the API returns a decision drift candidate.
- Given no extractable promises, the UI shows a useful empty state instead of failing.
- Given the same promise appears across multiple meetings, the API groups it into one chain.
- Given promises accumulate under one owner, the UI surfaces that owner as a risk hotspot.

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
- Use existing ZAI client/config patterns where AI generation is already used.
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

**Implementation status (2026-06-21)**: First backend and Flutter slice implemented. `POST /api/v1/qa/ask-across` normalizes the user's natural-language question into FTS keywords, searches existing minutes/summary/study-pack/sales-contact-brief search index rows across meetings, and returns a source-grounded synthesized answer with source task IDs, snippets, task types, and timestamps. The Flutter search screen now shows those sources in an "AI 근거 검색" panel above regular search results. If answer synthesis fails or returns empty content, the backend falls back to an extractive source summary instead of fabricating unsupported facts.

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

**Implementation status (2026-06-21)**: Backend, Flutter, search, and Obsidian slices implemented. `POST /api/v1/minutes/{task_id}/translation` translates persisted minutes or summary text into a target language, preserves speaker/timestamp/markdown structure in the prompt, stores results under `TaskResult.result_data["translations"]`, and `GET /api/v1/minutes/{task_id}/translation?target_language={language}` returns cached translations. The Flutter result screen now has a `번역` tab with summary/minutes source selection, target-language chips, cached result display, copy, and regenerate controls. Cached translation text is included in search indexing and Obsidian exports. Remaining work: broader multilingual transcript UX.

### P1: Summary Modes

Productize reusable summary modes such as executive brief, lecture notes, sales follow-up, sermon notes, research interview, action-only, and decision log.

**Implementation status (2026-06-21)**: Backend smart summary now exposes 12 selectable modes through `GET /api/v1/smart-summary/modes`, including executive, detailed, bullet, action-oriented, sentiment-focused, lecture notes, sales follow-up, sermon notes, research interview, decision log, action-only, and SOAP note. Generated mode-specific summaries are persisted under the source minutes result, `GET /api/v1/smart-summary/history/{minutes_task_id}` returns saved versions, and the Flutter result screen AI summary tab displays saved mode history across revisits while still supporting fresh generation. Domain-specific output tuning now gives sales follow-up, research interview, decision log, SOAP, lecture, and sermon modes more explicit labeled sections, safer fallbacks, grounded hypothesis wording, and healthcare scope warnings. Remaining work: validate output quality with real domain transcripts and user feedback.

### P1: YouTube and External Media Import

Add URL import and transcript generation for user-provided external media. This requires careful legal, content-source, and rate-limit handling.

**Implementation status (2026-06-21)**: Safe import slices implemented. `POST /api/v1/imports/external-text` accepts a user-provided `source_url`, title, source type, language, and transcript/text content, then persists it as a completed minutes-compatible artifact with Redis status/result cache, DB `TaskResult`, FTS search indexing, source metadata, and a standard `/api/v1/minutes/{task_id}` result URL. YouTube URLs are categorized as `youtube` without downloading or scraping platform content. Flutter `MinutesApi.importExternalText()` can call the endpoint, and the Home capture shortcuts now include a URL/Transcript sheet that adds imported content as a completed searchable meeting. That sheet can paste transcript text directly from the clipboard before import, and Android `ACTION_SEND` text/plain shares now open the app as a share target, pass the shared URL/text through a MethodChannel, and prefill the same safe URL/Transcript sheet. Remaining work: iOS share extension ingestion and a compliant transcript-fetch strategy for sources that explicitly permit it.

### P2: OCR Import

Import PDFs/images into searchable note context. This is useful for slides, handouts, receipts, whiteboards, and screenshots.

**Implementation status (2026-06-21)**: Product slice implemented. `POST /api/v1/imports/document` accepts user-owned PDF/DOCX/image uploads, validates extension and magic bytes, extracts full text with existing `pdfplumber`/`python-docx` capabilities, and can OCR PNG/JPG/JPEG/WebP/HEIC/HEIF images through an optional Pillow + pytesseract runtime. Extracted text routes through the existing external import pipeline so the document becomes a completed searchable minutes-compatible artifact. The Flutter Home capture shortcuts now include a PDF/DOCX/image picker that uploads the file and adds the imported artifact as a completed meeting. Android `ACTION_SEND` shares for PDF/DOCX/images now copy the shared content URI into app cache, pass the copied file path through the shared-import MethodChannel, and invoke the same document import/OCR flow. iOS now declares PDF/DOCX/image document types for Open In handoff, copies received files into the app temp cache, exposes them through the same shared-import MethodChannel, and invokes the existing document import/OCR path. When OCR runtime support is unavailable or extraction fails, image uploads return a deterministic 422 instead of creating empty notes. Remaining work: full iOS Share Extension UI for Safari/text shares.

### P2: Online Meeting Link Handoff

Provide a consent-first meeting-platform workflow for Zoom, Google Meet, and Microsoft Teams. The first product slice should not silently join calls or scrape meeting content; it should preserve the meeting link, make the next action explicit, and prepare the capture context.

**Implementation status (2026-06-21)**: Flutter Home can create scheduled online-meeting cards from Zoom/Meet/Teams links, show open/copy/calendar actions, and now routes shared Zoom/Meet/Teams URLs into the same pending card flow instead of the URL/Transcript import sheet. Remaining work: consent-aware meeting capture/bot integration and calendar-provider OAuth.

### P2: Apple Watch Quick Capture

Create a minimal Apple Watch companion for one-tap recording or recording trigger. This is a native-platform project and should wait until core mobile release evidence is complete.

### P1: Private-by-Default Ownership UX

Make note ownership and sharing state visible everywhere users make sharing decisions. This supports Owll-style private/team cloud expectations while preserving this project's privacy-first posture.

**Implementation status (2026-06-21)**: Flutter ownership visibility is in place for meeting cards, the result hero, and the team sharing decision surface, and server history sync now carries shared team IDs. `HistoryItem`/`HistoryDetailItem` include `shared_team_ids`, `MeetingListNotifier.refreshFromServer()` maps those IDs into `Meeting.sharedTeamIds` for new and existing local meetings, `MeetingCard` displays a `비공개` lock badge by default or `팀 공유` when one or more team IDs are present, the result hero resolves shared IDs through `teamListProvider` to show exact team names when available, and `TeamShareDialog` states that notes stay private unless selected teams are checked while showing `나만 볼 수 있음` or the active shared-team count. Team records now persist a `sharing_policy` with a safe `private` default or explicit `team_default` setting, API responses expose that policy, and Flutter marks teams that are policy defaults in the sharing dialog without silently sharing existing notes. Authenticated external text and document import flows now apply `team_default` policies only to newly created task artifacts, create a private owner record when no defaults apply, skip duplicate team shares, return `shared_team_ids`, and the Home meeting card reflects the team-shared state immediately. Remaining work: reuse the same policy hook from future native capture surfaces.

### P3: Domain Packs

Add optional sales/contact follow-up and SOAP-style healthcare templates as configurable modes, without making regulated claims.

**Implementation status (2026-06-21)**: Sales follow-up and SOAP note are available as smart-summary modes. Sales follow-up now separates customer needs, pain points/issues, objections, follow-up actions, next actions, and a grounded follow-up message draft when labeled transcript lines are present. SOAP note structures user-provided content into Subjective, Objective, Assessment 후보, Plan, and Safety / Scope sections, and explicitly states that it is for record organization only and does not generate medical judgment, diagnosis, prescription, or emergency judgment. `POST /api/v1/minutes/{task_id}/sales-contact-brief` now extracts a transcript-grounded customer/contact brief with contact identity, deal stage, customer needs, pain points, objections, next steps, follow-up message draft, and source references; `GET /api/v1/minutes/{task_id}/sales-contact-brief` returns the cached brief. Generated sales briefs are indexed as `sales_contact_brief` search artifacts, so customer/company/need/follow-up terms appear in normal search and cross-meeting Q&A evidence without replacing the source minutes row. Generated and revisited briefs are also persisted as `TaskResult.task_type="sales_contact_brief"` artifacts, and `GET /api/v1/sales-contacts` returns a paginated/queryable customer follow-up list with source task IDs, contact/deal fields, needs, pain points, next steps, follow-up message, and user-managed CRM status/notes; `PATCH /api/v1/sales-contacts/{artifact_task_id}/crm` persists lightweight CRM status/notes on the generated artifact, and list/search filtering includes those CRM notes. `GET /api/v1/sales-contacts/export.csv` exports matching contacts as CRM-importable CSV with identity, deal, needs, next-step, follow-up, CRM status/note, and source IDs. Flutter Result screen exposes the brief in a `영업` tab with customer/deal summary, copyable contact-field confirmation for name/company/role/email/phone, individual email/phone copy controls, sections for needs/pain points/objections/next actions, follow-up copy, clipboard export, regenerate, loading/error/empty states, and cache-miss auto-generation; Flutter also exposes a `영업 고객` entry point and `/sales-contacts` screen with search, refresh, lifecycle-stage filters, open/urgent/closed counts, customer/deal cards, needs chips, next action, follow-up message preview, editable CRM status/notes, CRM CSV share, and deep links back to source results. Flutter Home now has a `명함 스캔` shortcut that can capture a native camera photo or select an image file, reuses OCR document import, saves the imported artifact as a completed `명함 - ...` note, and points the user to the Result-screen sales tab for generated contact follow-up. Remaining work: external CRM OAuth/API sync and regulated clinical workflow validation remain out of scope for the current local-first benchmark slice.

## 7. Implementation Plan

1. Backend RED tests for study-pack schema and API.
2. Backend service implementation using existing summary/ZAI patterns.
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
