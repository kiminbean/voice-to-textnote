# Owll Benchmark PRD

**Status**: Study Pack core implemented; Cross-Meeting Q&A evidence search and synthesis exposed in search; sales follow-up briefs are searchable and listable; 2026-06-30 benchmark refreshed; Promise Radar v16 Command Center, 500+ real-meeting accuracy, extraction recall gate, privacy/evidence gate, and evidence loop implemented
**Created**: 2026-06-21  
**Last verified**: 2026-07-02
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

**Implementation status (2026-07-02)**: Backend schema/service/API, route registration, Flutter API/model/provider, Result-screen `약속 레이더` tab, Home promise dashboard, and focused backend/Flutter tests are implemented. v2 added promise chains, owner-level risk, high-risk counts, and recurring promise follow-up questions. v3 added a persistent Promise Ledger, transcript/speaker/timestamp evidence, user confirmation/status correction, next-meeting briefing, internal reminder/calendar candidates, internal ActionItem conversion, and ZAI GLM-5.2 semantic normalization with deterministic fallback. v4 adds operational schema repair, merge/split UI and API, auditable ledger history, stronger semantic matching, expanded Korean due-date parsing, FCM due-promise dispatch, Home dashboard exposure, team-scoped ledger access, and release-gate regression coverage. v5 adds Promise Autopilot status assessment, per-promise confidence explanations, Google Calendar/ICS export, optional due-notification scheduler, team assignee suggestions, promise quality scores, and strict release E2E scenario coverage for these flows. v6 adds a Promise Learning Loop, operator-friendly timeline, pre-meeting Promise Brief, Daily/Weekly Digest, Evidence Lock enforcement, first external work-tool integration through Slack, and a labeled accuracy fixture/evaluator. v7 adds status-specific Learning Loop thresholds, Autopilot preview-before-confirm UX, 24-case golden accuracy set, speaker/owner alias graph, immutable Evidence Pack snapshots in ledger events, promise conflict detection, and Google Tasks dry-run/OAuth-token export. v8 expands the golden set to 60 cases, adds Autopilot Review Queue, conflict resolution UX/API, Evidence Pack Viewer, app-driven Google Tasks OAuth send, team automation policy, and scheduled digest push. v9 expands the golden set to 72 cases with Creative Commons Town Meeting TV meeting sources, persists Review Queue rejections, exposes latest Evidence Pack from ledger rows, adds Google Tasks tasklist selection and sync-back, requires admin role for team automation policy changes, and adds user opt-in Digest Push preferences. v10 expands the golden set to 172 cases, including 112 Creative Commons real-meeting/audio-derived labels from Town Meeting TV, adds an accuracy report endpoint/UI, Review Queue filters, Evidence Comparison audit view, digest local-time/quiet-hours enforcement, Google Tasks push-update, and ledger identity confidence. v11 adds real-device Promise Radar E2E evidence generation, route-registration regression coverage, pre-meeting checkpoints, honorific-aware assignee matching, ICS Promise ID tracing, Google Tasks sync contracts, Promise Radar Prometheus metrics, and a 179-case accuracy set that evaluates at 100% with 112 real-meeting labels. v12 adds Android Promise Radar device-gate automation, owner responsibility scores, recurring meeting series linking, pre-meeting Promise Brief push dispatch/scheduler hook, Flutter Result-screen responsibility/series sections, and route/model regression tests. v13 adds Android gate hardening, responsibility/series UI reinforcement, and the previous 1-7 device-oriented pass. v14 adds a single Promise Radar Command Center API/UI, Learning Loop v3 status-specific sample/false-positive metrics, Evidence Audit rollups, Google Tasks OAuth guide/focus items, duplicate digest/pre-meeting local-day protection, and a 193-case accuracy set with 126 Creative Commons real-meeting/audio-derived labels. v15 expands the accuracy baseline to 369 cases with 302 Creative Commons real-meeting/audio-derived labels, including Korean Welfare TV/DKO multi-speaker meeting/debate sources, and adds Command Center panels for Promise Memory Graph, Autopilot Shadow Mode, Evidence Permission privacy/export gating, and Team Scorecard. v16 expands the accuracy baseline to 569 cases with 502 real-meeting/audio-derived labels, adds a 50-case false-negative extraction recall gate, broadens extraction for string/dict action items and next steps, exposes Command Center actions, Google Tasks OAuth readiness, learning scope breakdown, and Memory Graph node/edge previews. The E2E evidence generator now verifies the Command Center v16 contract and 500+ real-meeting baseline. Android staging release validation confirmed the result-screen `약속 레이더` tab on `Redmi Note 9 Pro`; a missing tab with only 11 result tabs indicates a stale APK, not a missing feature.

### Problem

Meeting assistant apps summarize what happened in one meeting, but users often lose what changed between meetings: who promised what last time, whether the promise was repeated or ignored, and whether a decision silently drifted. This is the point where summaries fail as a workflow.

### Product Bet

Voice to TextNote should become the app that remembers meeting obligations over time, not just the app that writes cleaner notes.

### UX

- A new `약속 레이더` tab appears in the meeting result screen.
  - The Home screen shows a compact `약속 레이더` dashboard for open/high-risk/due-soon/overdue promises.
  - The Home dashboard also shows a compact Daily Promise Digest.
  - The recording screen can show a pre-meeting Promise Brief before the user starts recording.
- The tab shows:
  - risk score and headline
  - next-meeting briefing
  - editable promise ledger
  - merge, split, reminder, history, completion, blocked, confirmation, and ActionItem actions
  - transcript/speaker/timestamp evidence
  - owner-level promise risk
  - promise chains across meetings
  - follow-up questions for the next meeting
  - stale promises from previous meetings
  - repeated/carried-over promises
  - possible decision changes
  - current meeting promises
  - v16 controls for timeline, learning feedback (`오판`), Slack export, Google Tasks tasklist send/sync/update, Autopilot Review Queue filters/reject persistence, conflict signal comparison, Evidence Pack Viewer, Evidence Comparison, team automation policy, Digest preference, 500+ accuracy report, 50-case extraction recall report, Promise Memory Graph, Autopilot Shadow Mode, Evidence Permission gate, Team Scorecard, and the Command Center focus/action/evidence/learning panels

### Backend Contract

- Endpoint: `GET /api/v1/promise-radar/{summary_task_id}?limit=30`
- Ledger endpoints:
  - `GET /api/v1/promise-radar/ledger`
  - `GET /api/v1/promise-radar/dashboard`
  - `GET /api/v1/promise-radar/command-center`
  - `GET /api/v1/promise-radar/responsibility-scores`
  - `GET /api/v1/promise-radar/meeting-series`
  - `PATCH /api/v1/promise-radar/ledger/{entry_id}`
  - `GET /api/v1/promise-radar/briefing/next`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/calendar`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/action-item`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/merge`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/split`
  - `GET /api/v1/promise-radar/ledger/{entry_id}/history`
  - `POST /api/v1/promise-radar/ledger/notifications/due`
  - `POST /api/v1/promise-radar/autopilot/{task_id}`
  - `POST /api/v1/promise-radar/autopilot/{task_id}/preview`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/autopilot-confirm`
  - `GET /api/v1/promise-radar/ledger/{entry_id}/explain`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/calendar/export`
  - `GET /api/v1/promise-radar/ledger/{entry_id}/assignee-suggestions`
  - `GET /api/v1/promise-radar/learning-profile`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/learning-feedback`
  - `GET /api/v1/promise-radar/ledger/{entry_id}/timeline`
  - `GET /api/v1/promise-radar/briefing/pre-meeting`
  - `POST /api/v1/promise-radar/briefing/pre-meeting/notifications`
  - `GET /api/v1/promise-radar/digest?cadence=daily|weekly`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/external-task`
  - `POST /api/v1/promise-radar/ledger/{entry_id}/external-task/update`
  - `POST /api/v1/promise-radar/accuracy/evaluate`
  - `GET /api/v1/promise-radar/accuracy/report`
- Source data: persisted `TaskResult` summary rows using `action_items`, `key_decisions`, and `next_steps`.
- Access model: current task access is verified; previous meetings are filtered by current user ownership, guest session, or explicit team scope. Team-scoped ledger calls require `TeamMember` membership before any ledger row is returned or changed.
- Persistence model: `promise_ledger_entries` stores user/guest/team-scoped promises with status, owner, assigned user, due date, risk, occurrences, evidence, confirmation state, reminder/calendar metadata, notification send state, and ActionItem links. `promise_ledger_events` stores auditable detected/updated/merged/split/calendar/action/notification/autopilot/learning/external-export history.
- Operational migration model: Alembic revision `006_promise_radar_operational_ledger` creates/repairs the Promise Ledger and event tables for managed upgrades. `validate_startup()` still runs `Base.metadata.create_all`, then repairs legacy SQLite `promise_ledger_entries` tables by adding `team_id`, `assigned_user_id`, `notification_sent_at`, and the team/assignee indexes. This prevents the previous class of "code expects a new Ledger column but the local/server SQLite DB was created before the column existed" startup/runtime failure.
- Fallback principle: deterministic extraction remains the source of truth when ZAI is unavailable or returns invalid JSON.
- Matching model: deterministic matching normalizes Korean particles and common product/deployment/checklist synonyms, then combines token overlap, character n-grams, containment, and owner match bonus. Exact canonical keys are still preferred; fuzzy matching is only used inside the same scoped open ledger.
- Due-date model: the parser handles fixed dates (`YYYY-MM-DD`, `7월 3일`, `7/3`), relative dates (`오늘`, `내일`, `모레`, `3일 후`, `2주 후`), Korean weekdays (`이번/다음 주 화요일`, `금요일`), and `오전/오후 N시 N분`.
- Push model: due/reminder-ready open promises can be dispatched through the existing FCM `PushService` and `DeviceToken` table. Successful sends set `notification_sent_at` and create a `notification_sent` ledger event; invalid tokens are deactivated through the existing push token invalidation path.
- Scheduler model: pipeline completion still triggers best-effort due notification dispatch. A process-local background scheduler can also be enabled with `PROMISE_RADAR_NOTIFICATION_SCHEDULER_ENABLED=true`; interval and batch size are controlled by `PROMISE_RADAR_NOTIFICATION_SCHEDULER_INTERVAL_SECONDS` and `PROMISE_RADAR_NOTIFICATION_SCHEDULER_LIMIT`.
- v2 response additions:
  - `promise_chains`: grouped promise history with first/last seen timestamps, age, occurrence count, status, and risk level.
  - `owner_risks`: per-owner open/stale/recurring promise counts and risk score.
  - `high_risk_count`: number of high-risk chains/owners needing attention.
- v3 response additions:
  - `ledger_entries`: persisted editable obligations with status and evidence.
  - `next_meeting_briefing`: unresolved/high-risk promises and questions before the next meeting.
  - `semantic_enrichment_status`: whether ZAI semantic normalization was applied, unavailable, failed, or deterministic only.
  - `reminder_candidates`: internal reminder/calendar payloads derived from due dates.
  - `action_item_id`: internal ActionItem linkage when a promise is converted into a task.
- v4 response additions:
  - `team_id`, `assigned_user_id`, `notification_sent_at`, and `dismissed_reason` on ledger entries.
  - `PromiseLedgerHistoryEntry`: auditable event stream for each ledger entry.
  - `PromiseRadarDashboard`: Home/dashboard counts, owner hotspots, urgent promises, and recent changes.
  - `PromiseNotificationDispatchResponse`: FCM due-promise dispatch evidence.
- v5 response additions:
  - `PromiseAutopilotResponse` and `PromiseAutopilotAssessment`: automatic completed/delayed/changed/dismissed status assessment with confidence and rationale.
  - `PromiseMatchExplanation`: matched text, similarity, overlap terms, confidence factors, and source evidence for a ledger entry.
  - `PromiseCalendarExportResponse`: Google Calendar URL plus valid ICS event content for real calendar handoff.
  - `PromiseAssigneeSuggestion`: team user recommendations from owner-name matching and historical assignment.
  - `PromiseQualityScore`: actionability score and issues for each ledger entry.
- v6 response additions:
  - `PromiseLearningProfile` and `PromiseLearningFeedbackResponse`: scoped threshold, correction counts, owner aliases, and feedback recording.
  - `PromiseTimelineResponse`: readable lifecycle from first detection through repeats, delays, Autopilot assessment/application, user feedback, merge/split, calendar, push, and external export events.
  - `PromisePreMeetingBrief`: readiness score, top promises, and questions before recording.
  - `PromiseDigest`: daily/weekly open, overdue, due-soon, high-risk counts plus briefing lines.
  - `PromiseExternalExportResponse`: Slack payload dry-run or webhook send result.
  - `PromiseAccuracyEvaluation`: fixture-based status accuracy and per-status precision.
- v7 response additions:
  - `PromiseLearningProfile.status_thresholds`, `status_false_positive_count`, `status_confirmed_count`, and `owner_aliases`: status-specific learning plus speaker/owner/user alias graph.
  - `PromiseAutopilotAssessment.requires_confirmation`, `threshold`, `evidence_locked`, `conflict_detected`, `conflict_reason`, and `evidence_pack`: preview/confirmation safety metadata.
  - `PromiseAutopilotConfirmRequest`: applies one previewed assessment only after user confirmation.
  - `PromiseEvidencePack`: immutable snapshot of matched text, marker hits, source evidence, confidence factors, and capture time stored in ledger events.
  - `PromiseExternalExportRequest`/`Response`: Google Tasks tasklist/OAuth-token export fields, external id/url fields, and dry-run payload support.
- v8 response additions:
  - `PromiseAutopilotReviewQueue` and `PromiseAutopilotReviewItem`: queue-level counts plus ledger context and assessment evidence for batch review.
  - `PromiseConflictResolveRequest`: user-selected completed/delayed/changed/dismissed/open/blocked conflict resolution.
  - `PromiseAutomationPolicy` and `PromiseAutomationPolicyUpdateRequest`: scoped safe-auto, preview-only, completed-only, or manual-only policy.
  - `POST /api/v1/promise-radar/ledger/notifications/digest`: scheduled Daily/Weekly Digest FCM dispatch with daily dedupe.
- v9 response additions:
  - `PromiseAutopilotRejectRequest`: persists wrong review candidates so the same task/status suggestion is not shown again.
  - `PromiseDigestPreference` and `PromiseDigestPreferenceUpdateRequest`: user/team scoped scheduled digest opt-in preferences.
  - `PromiseGoogleTaskListResponse`, `PromiseExternalTaskSyncRequest`, and `PromiseExternalTaskSyncResponse`: Google Tasks tasklist selection and sync-back status.
  - `GET /api/v1/promise-radar/ledger/{entry_id}/evidence-pack`: latest immutable Evidence Pack lookup for ledger-row audit.
- v10 response additions:
  - `PromiseAccuracyReport`: fixture path, source manifest path, status/source counts, target threshold, real-meeting label count, and full evaluation summary.
  - `PromiseEvidenceComparison`: previous ledger evidence vs latest Evidence Pack text/similarity/shared terms for audit.
  - `PromiseExternalTaskUpdateRequest`: pushes the current Promise Ledger status/title back to Google Tasks without storing OAuth access tokens.
  - `PromiseLedgerEntryResponse.identity_confidence` and `identity_confidence_factors`: owner/speaker/assignee/voiceprint grounding visible in the ledger row.
  - `GET /api/v1/promise-radar/ledger/{entry_id}/evidence-comparison`, `POST /api/v1/promise-radar/ledger/{entry_id}/external-task/update`, and `GET /api/v1/promise-radar/accuracy/report`.

### Acceptance Criteria

- Given a current summary with action items, the tab lists current promises.
- Given a previous similar action item, the API returns it as a carried-over promise.
- Given a previous action item absent from the current meeting, the API returns it as stale and creates a follow-up question.
- Given related but changed decisions, the API returns a decision drift candidate.
- Given no extractable promises, the UI shows a useful empty state instead of failing.
- Given the same promise appears across multiple meetings, the API groups it into one chain.
- Given promises accumulate under one owner, the UI surfaces that owner as a risk hotspot.
- Given a logged-in or guest-scoped user opens Promise Radar, current promises are upserted into the persistent Promise Ledger.
- Given a transcript/minutes source contains matching segments, each ledger entry includes speaker, timestamp, transcript, and meeting link evidence.
- Given the user marks a promise completed/blocked/confirmed, the ledger status updates and the Promise Radar tab refreshes.
- Given unresolved promises exist, the next-meeting briefing returns high-risk/overdue/due-soon counts, owner hotspots, questions, and reminder candidates.
- Given a logged-in user turns a promise into a task, the backend creates one internal ActionItem and remembers the link idempotently.
- Given ZAI GLM-5.2 is configured, semantic normalization may improve canonical promise matching; if it fails, deterministic matching still returns a usable radar.
- Given two ledger promises represent the same obligation, the user can merge them; the source entry is dismissed with `merged_into:<target_id>`, evidence/occurrences are preserved on the target, and both sides get history events.
- Given one ledger promise contains two obligations, the user can split it into a new tracked entry with owner/due-date edits and history.
- Given the user opens a ledger entry history, the app can show update, merge, split, calendar, ActionItem, and push notification events.
- Given an old SQLite DB is started after v4 code is deployed, startup schema repair adds missing Promise Ledger v4 columns/indexes without deleting data.
- Given an open promise reaches its due/reminder time and a user has active FCM tokens, due-promise dispatch sends a real push and marks the ledger item as notified.
- Given a team ID is supplied, Promise Radar ledger/dashboard/briefing/update operations are scoped to that team only after membership is verified.
- Given the user runs Promise Autopilot after a follow-up meeting, high-confidence completed/delayed/changed/dismissed statuses are applied and recorded as ledger events.
- Given the user asks why a promise was matched, the app shows similarity, overlap terms, confidence factors, and source evidence.
- Given a promise has a due/reminder time, the app can open Google Calendar or provide ICS event content.
- Given a team-scoped promise has an extracted owner, the app can recommend matching team users and expose the quality score gaps that should be fixed.
- Given the user marks an automatic decision as wrong, the learning loop records `learning_feedback`, raises/adjusts the scoped Autopilot threshold, and exposes the profile through API/UI.
- Given the user opens a promise timeline, the app shows first detection, update/repeat, delay, Autopilot, user confirmation/feedback, merge/split, calendar, push, and external export events as a readable lifecycle.
- Given the user is about to record, the recording screen can show the top unresolved promises/questions from the pre-meeting brief.
- Given the user opens Home, the app can show a daily digest summary of open, overdue, due-soon, and high-risk promises.
- Given Autopilot suggests a state change, Evidence Lock prevents automatic mutation unless matched text, source evidence, sufficient similarity, and confidence factors exist. Weak cases remain visible as assessments only.
- Given Autopilot suggests a state change in the Flutter Result screen, the app shows a preview first; only a user `맞음` confirmation calls `autopilot-confirm` and mutates the ledger.
- Given multiple Autopilot candidates exist, the app shows them in a Review Queue where the user can confirm all safe candidates, reject wrong candidates for learning, inspect Evidence Pack details, or resolve conflicts. Rejected candidates are stored as `autopilot_review_rejected` and do not reappear for the same task/status candidate.
- Given users correct completed/delayed/changed/dismissed outcomes, Learning Loop v3 adjusts only the affected status threshold, tracks per-status sample counts and false-positive rates, and exposes alias/evidence-lock health instead of moving all Autopilot thresholds together.
- Given a promise has speaker labels/profiles, owner names, and assigned users, the learning profile exposes an alias graph and assignee suggestions normalize Korean honorific aliases such as `기수님`.
- Given source text contains conflicting state signals such as completed and delayed markers together, Promise Radar marks a conflict, shows side-by-side signal evidence in the Review Queue, and does not auto-apply the state.
- Given a conflict is shown, the user can choose 완료/지연/변경/제외 or open the split-recommended flow; the decision is stored as `conflict_resolved`.
- Given an Autopilot decision is applied or confirmed, the ledger event stores an immutable Evidence Pack so the decision can be audited later from Review Queue or `GET /api/v1/promise-radar/ledger/{entry_id}/evidence-pack`.
- Given a promise should move to an external work tool, Slack dry-run generates a payload without sending; non-dry-run requires `PROMISE_RADAR_SLACK_WEBHOOK_URL`. Google Tasks uses app-driven Google OAuth scope approval, lets the user choose a tasklist, sends through the backend with a one-request access token, stores external task metadata, and can sync completed Google Tasks back to the Promise Ledger.
- Given a team wants different automation risk tolerance, `GET|PUT /api/v1/promise-radar/automation-policy` stores safe-auto, preview-only, completed-only, or manual-only policy as auditable ledger events; team-scoped updates require an admin team member.
- Given scheduled digest push is enabled with `PROMISE_RADAR_DIGEST_PUSH_ENABLED=true`, the scheduler sends Daily/Weekly Promise Digest FCM pushes only for users who enabled `GET|PUT /api/v1/promise-radar/digest-preference` and suppresses duplicate sends for the same user/cadence/day.
- Given pre-meeting brief push is enabled with `PROMISE_RADAR_PRE_MEETING_PUSH_ENABLED=true`, the scheduler sends `promise_radar_pre_meeting_brief` FCM data once per user/day without consuming due-promise `notification_sent_at`.
- Given the Command Center is opened, the app loads dashboard, review queue, learning insight, digest, pre-meeting brief, external-task reconcile, accuracy report, extraction recall report, Evidence Audit, Promise Memory Graph, Autopilot Shadow Mode, Evidence Permission gate, Team Scorecard, Google Tasks OAuth guide/readiness, operator actions, and prioritized focus items from one endpoint.
- Given the dashboard or next-meeting briefing is requested, the response includes owner responsibility scores and recurring meeting series inferred from ledger status, due dates, occurrences, and source meeting titles without requiring a DB migration.
- Given Android release menu visibility is checked, `client/scripts/verify_promise_radar_device_gate.py` verifies install metadata, UIAutomator `약속 레이더`/`탭 12개`, and APK staging URL guard.
- Given Promise Radar rules change, `backend/tests/fixtures/promise_radar_accuracy_cases.json` and `backend/scripts/evaluate_promise_radar_accuracy.py` measure labeled status accuracy before release. The current golden set has 569 cases, including 502 labels derived from Creative Commons YouTube real meeting/audio sources documented in `backend/tests/fixtures/promise_radar_real_meeting_sources.json`. `backend/tests/fixtures/promise_radar_extraction_cases.json` and `backend/scripts/evaluate_promise_radar_extraction.py` separately measure false-negative extraction recall with 50 cases. The v16 set mixes English Town Meeting TV meetings and Korean Welfare TV/DKO multi-speaker meeting/debate sources.
- Given strict release evidence is collected, Promise Radar Autopilot, due push, calendar export, and assignee/quality display must each have Android/iOS physical-device observations.
- Given release-gate checks are run, `ruff`, targeted Promise Radar backend tests, accuracy evaluator, compile/route loading, Flutter analyze, and Flutter model/result-screen tests pass.

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
