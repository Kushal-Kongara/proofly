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

## Future Responsibilities of Each Service

### FastAPI backend
The system of record and the only service holding API keys. Responsible for:
- Serving document vault, timeline, chat, and O-1A planner endpoints.
- Orchestrating calls to Supermemory, Featherless, and Tavily.
- Enforcing that every AI-derived fact carries a source citation, confidence
  score, and verification status before it's returned to the frontend.

### Supermemory
Document/fact memory layer for the RAG pipeline. As of Phase 2, uploaded
documents are ingested into Supermemory (see "Ingestion flow" above) and
their processing status is surfaced back to the vault UI. Retrieving that
content back out for the chatbot and O-1A planner — grounding answers in
the user's own documents instead of relying on model memory alone — is
still a future phase.

### Featherless
Hosted LLM inference provider. Will run the extraction (document → structured
facts), the document-grounded chatbot's generation step, and O-1A
evidence-mapping reasoning. Referenced only via `FEATHERLESS_API_KEY` /
`FEATHERLESS_BASE_URL` — the backend never hardcodes model calls with
inline secrets.

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
