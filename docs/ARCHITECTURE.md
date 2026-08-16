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

## Future Responsibilities of Each Service

### FastAPI backend
The system of record and the only service holding API keys. Responsible for:
- Serving document vault, timeline, chat, and O-1A planner endpoints.
- Orchestrating calls to Supermemory, Featherless, and Tavily.
- Enforcing that every AI-derived fact carries a source citation, confidence
  score, and verification status before it's returned to the frontend.

### Supermemory
Document/fact memory layer for the RAG pipeline. Will store parsed document
content and extracted facts so the chatbot and planner can retrieve
user-specific, document-grounded context instead of relying on model
memory alone.

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
