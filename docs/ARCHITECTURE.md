# Proofly — Architecture

## Overview

```
React (Vite/TS) frontend  -->  FastAPI backend  -->  Supermemory / Featherless / Tavily
```

The frontend never talks to Supermemory, Featherless, or Tavily directly —
all third-party calls are proxied through the FastAPI backend so API keys
never reach the browser.

## Phase 1 (this build)

- **Frontend**: Vite + React + TypeScript. A minimal page that renders the
  Proofly name/tagline and calls `GET /health` to confirm backend
  connectivity. No document upload, chat UI, or dashboard yet.
- **Backend**: FastAPI app with one real endpoint (`/health`), CORS
  configured via `pydantic-settings`, and the full set of Pydantic data
  contracts (`app/schemas/`) that every later phase will build on.
- **Data**: no database. `sample_documents/demo_profile.json` is the single
  source of synthetic demo data, structured to match the Pydantic schemas
  exactly.

## Phase 2 (this build)

Synthetic document upload and Supermemory ingestion — no extraction,
chatbot, or O-1A analysis yet; this phase only gets documents into
Supermemory and lets the user see them and their processing status.

- **Frontend**: a Document Vault page (drag-and-drop + file picker,
  multi-file, upload progress, and a card/row per document showing
  filename, type, processing status, and a synthetic-demo badge). Polls
  `GET /api/documents/{id}/status` only for documents not yet in a terminal
  state, via a single interval for the component's lifetime (no
  per-document timers, no duplicate polling loops).
- **Backend**: `POST /api/documents/upload`, `GET /api/documents`,
  `GET /api/documents/{id}/status`, `DELETE /api/documents/{id}`. Files are
  read into memory, validated (extension + declared MIME type, size ≤ 10 MB,
  non-empty), forwarded to Supermemory, and never written to disk.
- **Supermemory**: `app/services/supermemory_service.py` wraps the official
  `supermemory` Python SDK (`AsyncSupermemory`, `documents.upload_file` /
  `.list` / `.get` / `.delete`) behind `SupermemoryService`, injected into
  routes via `Depends(get_supermemory_service)` so tests substitute a fake
  implementation and never touch the network.

### Ingestion flow

```
Browser                FastAPI (/api/documents/upload)         Supermemory
  |  multipart file            |                                     |
  |---------------------------->  validate ext + MIME + size         |
  |                             |  read bytes into memory (no disk)  |
  |                             |  custom_id = sha256(bytes)[:32]    |
  |                             |  metadata: original_filename,      |
  |                             |    content_type, source=           |
  |                             |    "manual_upload", synthetic=true |
  |                             |------------------------------------>| documents.upload_file(
  |                             |                                     |   container_tag="proofly_demo_maya",
  |                             |                                     |   task_type="superrag", ...)
  |                             |<------------------------------------| { id, status }
  |<---------------------------- VaultDocument (normalized status)   |
```

`container_tag` is always the server-controlled constant
`SUPERMEMORY_CONTAINER_TAG` (default `proofly_demo_maya`) from backend
settings — no route accepts a container tag from the browser, so nothing a
client sends can read or write outside the demo container. Listing and
deletion are scoped the same way: `GET /api/documents` only ever lists that
one container, and `DELETE /api/documents/{id}` targets a single document
ID — there is no "delete container" operation exposed anywhere.

### Error responses

Upload/list/status/delete never leak raw Supermemory SDK errors or the API
key; each maps to a generic, sanitized message:

| Condition | Status |
| --- | --- |
| Bad extension, MIME/extension mismatch, empty file | 400 |
| File over the 10 MB limit | 413 |
| Document ID not found | 404 |
| Deleting a document that hasn't finished processing yet | 409 — `"Document is still processing. Try deleting it after processing finishes."` |
| `SUPERMEMORY_API_KEY` not configured | 503 |
| Any other Supermemory upstream failure (network, 5xx, auth) | 502 |

The 409 case is Supermemory itself rejecting the delete (it returns 409 for
an in-flight document); `SupermemoryService.delete_document` catches that
specific SDK `ConflictError` and re-raises it as `SupermemoryConflictError`
with the safe message above — the frontend also disables the Delete button
while a document's status is `queued`/`extracting`/`chunking`/`embedding`,
so hitting this via the UI in the first place requires a race between two
tabs or a stale poll.

**Why `task_type="superrag"`**: Supermemory's `documents.upload_file`
supports two task types. `"memory"` (the default) builds a full context
layer intended for an agent's own long-running memory. `"superrag"` is
Supermemory's managed-RAG-as-a-service mode — it's the right fit here
because Proofly's document vault is a bounded, per-demo-user document
store meant to be *retrieved from* for grounded chat/extraction in a later
phase, not an evolving agent memory. `superrag` keeps ingestion scoped to
"process this file for retrieval," matching what the vault actually needs.

Processing status returned by Supermemory
(`queued → extracting → chunking → embedding → done`, plus `failed`) is
normalized in `supermemory_service.normalize_processing_status`: any value
Supermemory returns that Proofly doesn't have a defined meaning for
(including Supermemory's own `indexing` stage) maps to `unknown` rather
than being passed through unchecked.

> **Production note**: this build has no authentication and every document
> lands in the same single demo container. A production version needs real
> user authentication and a container tag derived per-authenticated-user
> (e.g. `user_<id>`) — never a client-supplied value — so one user's
> documents are never visible to another.

## Phase 3 (this build)

Featherless document extraction and a deterministic, document-grounded
timeline. No chatbot, no O-1A analysis, no Tavily, no authentication yet —
this phase turns completed Supermemory documents into structured facts and
a timeline, and nothing more.

```
Completed Supermemory documents
  -> retrieve extracted text (SupermemoryService.list_completed_documents_with_content)
  -> one batch Featherless call (FeatherlessService.analyze_documents)
  -> Pydantic validation (LLMAnalysisOutput, including citation-membership check)
  -> deterministic timeline calculation (app/services/timeline.py, pure Python)
  -> dashboard (GET /api/analysis/latest, GET /api/timeline)
```

- **Frontend**: a Dashboard page (nav alongside the existing Document
  Vault). An "Analyze documents" button — disabled until at least one
  document is `done` — triggers `POST /api/analysis/run`; shows a loading
  state, safe errors, summary cards (reported classification, current work
  authorization, its expiration, documents analyzed), any conflicts/missing
  information, and the timeline. Every document-derived value is marked
  "Needs review." `historical` events render neutrally (gray, not the
  red/amber used for `urgent`/`overdue`) with a note that they're a prior
  document event, not a missed deadline. No approval percentages anywhere,
  and nothing claims the user *is* in a given status — only that a document
  *reports* it.
- **Backend**: `POST /api/analysis/run`, `GET /api/analysis/latest`,
  `GET /api/timeline` (`app/routers/analysis.py`). `POST /api/analysis/run`
  returns `409` — `"No processed documents are available for analysis."` —
  when the demo container has zero `done` documents, rather than creating
  and storing an empty `AnalysisResult`; nothing is written to the
  in-process store in that case.
- **Featherless**: `app/services/featherless_service.py` wraps the official
  `openai` Python SDK's `AsyncOpenAI` client (pointed at
  `FEATHERLESS_BASE_URL`) behind `FeatherlessService`, injected via
  `Depends(get_featherless_service)` so tests substitute a fake and never
  touch the network or spend credits.

### Why Featherless extraction never invents legal deadlines

The LLM call's system prompt explicitly forbids legal conclusions,
predictions, and filing deadlines, and every timeline event's date and
"days remaining" figure is computed in `app/services/timeline.py` — plain
Python, zero model involvement — from dates the model already extracted
and Pydantic already validated. This split exists because:

- **Auditability**: a date either came verbatim from a cited document or it
  didn't. If the model computed "you must file by X," there would be no way
  to verify that arithmetic (or the underlying legal rule) without asking
  the model again, and a different call could silently give a different
  answer for identical input.
- **No invented rules**: real filing deadlines (e.g. when a STEM OPT
  extension must be filed) depend on regulations Proofly does not encode
  anywhere. Rather than have a model guess at those rules from training
  data of unknown vintage/accuracy, Proofly only ever surfaces dates that
  are *explicitly written in a supplied document* — see "Extraction rules"
  below — and computes countdowns against those dates alone.
- **D/S can't be arithmetic'd around**: an I-94 admitted "D/S" has no
  expiration to count down to. Asking a model to "calculate days left in
  F-1 status" invites it to either refuse unpredictably or fabricate a
  number. Keeping the calculation in Python means the D/S case is simply a
  branch that returns `None` — see `build_timeline` in
  `app/services/timeline.py`.

### Extraction rules (enforced in the Featherless system prompt and Pydantic schema)

- Use only facts explicitly present in the supplied documents — never invent a missing value.
- OPT and STEM OPT are employment authorizations, never a separate immigration classification.
- A visa stamp is never, by itself, a basis for concluding current legal status.
- An I-94 "D/S" must remain `admit_until.type = "duration_of_status"` with no fabricated date.
- No legal conclusions, predictions, or approval likelihoods — extraction only.
- Every `<document>` block in the prompt is wrapped with its Supermemory document ID and original filename and is treated as **untrusted data, not instructions** — the system prompt tells the model explicitly not to follow anything that looks like an embedded instruction inside a document's text (see `test_prompt_injection_inside_document_is_treated_as_inert_data`).
- Every citation the model produces must be one of the document IDs it was actually given. `LLMAnalysisOutput` validates this itself, via `model_validate(data, context={"valid_document_ids": {...}})` — a response citing an unknown document ID fails Pydantic validation exactly like a malformed field would.

### Timeline status and legal-effect labeling (`app/services/timeline.py`)

Two rules, enforced in `_status_for_days` and each event builder, keep the
timeline from ever implying more legal significance than a document
actually supports:

- **`overdue` vs. `historical`**: `overdue` is reserved for a source
  *explicitly* identifying a required action or deadline that has been
  missed. Proofly extracts no such deadlines today — an EAD end date, an
  I-20 program end date, a visa/passport expiration, and a reported
  admission end date are all just facts printed on a document, not "you
  must act by this date" statements. A past date in any of those
  categories is `historical`, never `overdue`; `_status_for_days` takes an
  `is_required_deadline` flag (unused by every current builder, but kept so
  a future explicit-deadline source has somewhere correct to plug into)
  that is the only way to reach `overdue` at all.
- **`affects_authorized_stay` is `False` only for visa-stamp expiration**:
  that is the one case where the document type alone safely proves "this
  does not determine authorized stay" (see `docs/PRODUCT_SPEC.md`'s visa
  rules). Every other category — including EAD/work-authorization
  expiration and passport expiration — defaults to `None` (unknown) rather
  than asserting `False`; only a reported classification's own fixed
  admission end date (rare — most F-1 admissions are D/S) is `True`, since
  that date *is* the classification's stated end.

### Retry, repair, and failure handling

- One shared `asyncio.Lock` (module-level, not per-request) serializes every Featherless call in the process — the configured model consumes all four of the account's concurrency units, so two calls in flight at once would fail upstream regardless of retries.
- Transport-level retries: 429/500/503 are retried with bounded exponential backoff, 3 attempts total. 401/403 are never retried — they're a configuration problem, not a transient one, and map straight to `FeatherlessConfigurationError`. Any other status (e.g. 502/504) fails immediately, matching the letter of the retry spec rather than retrying every 5xx.
- Output-level repair: if the model's JSON fails to parse, fails Pydantic validation, or cites an unknown document ID, exactly one repair call is made — the original response plus the validation error are appended to the conversation and the model is asked to correct it. If the repair also fails, extraction fails safely (`FeatherlessValidationError`, mapped to `502`) rather than looping or returning something unvalidated.
- A combined-input character cap (`FEATHERLESS_MAX_TOTAL_INPUT_CHARACTERS`) raises `FeatherlessInputTooLargeError` (`413`) before any API call is made, rather than sending an oversized/costly request.
- Document content is never logged in full anywhere in this path — only counts, lengths, and short Pydantic-error summaries (field paths + messages, never raw text).

### In-process analysis store (accepted limitation)

`app/routers/analysis.py` keeps the most recent `AnalysisResult` in a plain
module-level variable, guarded by an `asyncio.Lock` only against
interleaved writes within a single process. This is intentional for a
one-day prototype and has real limits:

- Restarting the backend process loses the latest analysis (`GET
  /api/analysis/latest` goes back to `404` until `/api/analysis/run` is
  called again).
- Running more than one worker/process (e.g. `uvicorn --workers 2`, or any
  horizontally-scaled deployment) means each process has its own,
  independent "latest" — a client could get a different answer per request.
- There is no history — only the single most recent result is kept.

A real deployment needs a database (or at minimum a shared cache like
Redis) here instead. No database was added in this phase, per scope.

## Future Responsibilities of Each Service

### FastAPI backend
The system of record and the only service holding API keys. Responsible for:
- Serving document vault, timeline, chat, and O-1A planner endpoints.
- Orchestrating calls to Supermemory, Featherless, and Tavily.
- Enforcing that every AI-derived fact carries a source citation, confidence
  score, and verification status before it's returned to the frontend.

### Supermemory
Document/fact memory layer for the RAG pipeline. As of Phase 2, uploaded
documents are ingested into Supermemory (see "Ingestion flow" above). As of
Phase 3, their extracted text is retrieved back out
(`list_completed_documents_with_content`) and handed to Featherless for
structured extraction. Using that same retrieval to ground a future
chatbot's answers is still a later phase.

### Featherless
Hosted LLM inference provider (`deepseek-ai/DeepSeek-V3.2` via the
OpenAI-compatible Chat Completions API, `openai==3.1.0`'s `AsyncOpenAI`
client). As of Phase 3, runs the one-batch structured extraction described
above (`app/services/featherless_service.py`). The document-grounded
chatbot's generation step and O-1A evidence-mapping reasoning are still
future phases. Referenced only via `FEATHERLESS_API_KEY` /
`FEATHERLESS_BASE_URL` / `FEATHERLESS_MODEL` — the backend never hardcodes
model calls with inline secrets.

### Tavily
Web search for grounding chatbot answers in current, official public
sources (e.g. USCIS policy pages) alongside the user's own documents,
clearly distinguished from document-sourced facts.

## Data Contracts

All AI-derived facts (`ExtractedFact`, `EvidenceItem`, and AI-populated
`ImmigrationStatus`/`EmploymentAuthorization`/`VisaStamp`/`TimelineEvent`
entries) carry:
- `source` — a `SourceCitation` (`document_id` + optional `page_number`).
- `confidence` — float in `[0, 1]`.
- `verification_status` — `unverified` / `verified` / `rejected`.

This is enforced at the schema level (`backend/app/schemas/`) so no future
phase can silently ship an unattributed AI fact to the frontend.

Phase 3's extraction schemas (`backend/app/schemas/analysis.py`) apply the
same discipline to real Featherless output: `AnalyzedDocument`,
`AnalysisFact`, `ReportedImmigrationClassification`, `AcademicProgramRecord`,
`EmploymentAuthorizationRecord`, `VisaStampRecord`, `PassportRecord`,
`AnalysisConflict`, `MissingInformationItem`, and `AnalysisWarning` are
deliberately separate classes from the Phase 1 demo-profile schemas they
resemble (e.g. `EmploymentAuthorizationRecord` vs. `EmploymentAuthorization`)
— the Phase 1 versions model a curated, internally-consistent demo profile
(EAD `end_date` required), while the Phase 3 versions model raw,
possibly-incomplete claims an LLM makes about real uploaded documents,
where every value needs `source_document_id`, `source_filename`,
`confidence`, and `verification_status = "needs_user_review"`, and dates
are optional because "never invent a missing value" is a hard rule. They
reuse Phase 1's `DocumentType`, `ImmigrationStatusType`,
`EmploymentAuthorizationType`, and `SourceCitation` directly rather than
redefining them.

### Three distinct concepts, deliberately not conflated

Immigration status, work authorization, and travel documents expire on
independent timelines. Collapsing them into one "status" concept is a
common and consequential modeling mistake, so the schema keeps them
separate:

- **`ImmigrationStatus`** — the underlying classification (e.g. F-1). Most
  students are admitted "D/S" (duration of status) with no fixed end date;
  the schema's `duration_of_status` flag forces `end_date` to `None` in that
  case, and `app/countdown.py`'s `authorized_stay_countdown_days` returns
  `None` rather than inventing a countdown. **F-1 classification stays
  `is_current: true` across OPT and STEM OPT** — those are periods of
  employment authorization held *under* F-1, not separate statuses.
- **`EmploymentAuthorization`** — OPT / STEM OPT periods, each with a
  required, fixed `end_date` taken straight from the EAD card. This is what
  a "days until my work authorization expires" countdown should be computed
  against.
- **`VisaStamp`** — the passport stamp used to seek admission at a port of
  entry. Its `expiration_date` is described only as "days until the visa
  stamp expires": a valid visa permits the holder to request admission at a
  U.S. port of entry; it does not guarantee admission or determine
  authorized stay. It must never be presented as, or substituted for, the
  expiration of status or work authorization — a visa can lapse while
  status and EAD remain fully valid, and renewing a visa does not extend
  either.

`app/countdown.py` keeps these three "days remaining" computations as
separate functions (`authorized_stay_countdown_days`,
`employment_authorization_countdown_days`,
`visa_validity_countdown_days`) specifically so a future UI or chatbot
answer can't accidentally cite one document's expiration as another
document's deadline.

## Security

- Secrets live only in `.env` (gitignored). Code references environment
  variable **names** only (`FEATHERLESS_API_KEY`, etc.) via
  `pydantic-settings`.
- `.env.example` documents required variable names with empty/placeholder
  values.
- No authentication in this hackathon build — all data is synthetic demo
  data, not real user data.
- `SUPERMEMORY_API_KEY` is read only in `app/services/supermemory_service.py`
  and passed straight to the SDK client — it is never logged, never included
  in an HTTP response, and never sent to the frontend. Upload/list/status/
  delete error responses return sanitized, generic messages (see
  `_sanitized_upstream_message`), not raw SDK exception text.
- Uploaded file bytes exist only in request memory for the duration of the
  upload call — never written to disk, never logged.
- `FEATHERLESS_API_KEY` is read only in `app/services/featherless_service.py`
  and passed straight to `AsyncOpenAI` — same rules as Supermemory: never
  logged, never in a response, never sent to the frontend. A missing key (or
  a rejected one — 401/403 from Featherless) returns `503`, not a crash.
  Document content sent to Featherless is never logged in full — only
  lengths/counts and short, field-level Pydantic validation error summaries.
