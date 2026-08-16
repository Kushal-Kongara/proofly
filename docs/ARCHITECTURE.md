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

## Phase 4 (this build)

The O-1A evidence-readiness planner. No chatbot, no Tavily, no EB-1, no
authentication — this phase turns completed Supermemory documents into a
document-coverage assessment against the eight O-1A criteria and a
prioritized evidence-gathering action plan, and nothing more.

```
Completed Supermemory documents
  -> retrieve extracted text (SupermemoryService.list_completed_documents_with_content)
  -> one batch Featherless call (FeatherlessService.analyze_o1_evidence)
  -> Pydantic validation (O1LLMAnalysisOutput, citation-membership check)
  -> deterministic evidence-coverage assessment (app/services/o1_assessment.py, pure Python)
  -> O-1 Plan UI (GET /api/o1/criteria, POST /api/o1/assessment/run, GET /api/o1/assessment/latest)
```

### Product principle: evidence coverage, never legal eligibility

Proofly organizes evidence and identifies gaps. It **never** predicts
approval, computes an eligibility percentage, or states that a criterion
is legally satisfied — those are for a human immigration attorney. This is
enforced at three layers, not just in prose:

1. **Vocabulary is closed at the schema level.** `O1CriterionStatus` only
   has four values — `documented_support_found`, `partial_support_found`,
   `no_support_found`, `needs_expert_review` — and the words `eligible`,
   `ineligible`, `approved`, `denied`, `criterion_satisfied`,
   `approval_chance`, `probability`, and any percentage/score field do not
   exist anywhere in `app/schemas/o1_assessment.py`. There is no field to
   put that value in even if a model tried to return one.
2. **The model never computes a status, a count, or a coverage label.**
   Featherless (`FeatherlessService.analyze_o1_evidence`) only ever returns
   `O1LLMAnalysisOutput` — raw evidence facts (`title`, `factual_summary`,
   `criterion_id`, `evidence_role`, `limitations`, `date`,
   `is_one_time_major_achievement`, `is_comparable_evidence`,
   `flag_for_expert_review`). Every `O1CriterionAssessment.status`, every
   `O1AssessmentSummary` count, `documentation_coverage`, and the action
   plan are computed in `app/services/o1_assessment.py` — plain Python, no
   model call — from those raw facts. See "Deterministic status
   derivation" below.
3. **Every criterion assessment is marked `requires_attorney_review: true`**,
   and every response carries the fixed disclaimer **"Document coverage is
   not a determination that any USCIS criterion is satisfied."** plus "An
   attorney must evaluate the complete case."

### The eight static criteria (never model-generated)

`app/data/o1_criteria.py` hardcodes the eight regulatory O-1A criteria
(8 CFR 214.2(o)(3)(iii)) as `O1CriterionDefinition` records — `code`,
`name`, `regulatory_description`, `official_sources` — plus two
informational (non-criterion) categories, `O1_ONE_TIME_ACHIEVEMENT` and
`O1_COMPARABLE_EVIDENCE`. `app/services/o1_assessment.build_o1_assessment`
always iterates this static list to build all eight
`O1CriterionAssessment` entries, regardless of what the model returned —
so a criterion with zero evidence is still present (`no_support_found`),
and a Featherless response can never rename, reword, or drop a criterion
definition (`O1LLMAnalysisOutput` only lets the model *cite* a criterion
by its `O1CriterionCode` enum value; it has no field for a definition
string at all). Source:
[O-1 visa overview](https://www.uscis.gov/working-in-the-united-states/temporary-workers/o-1-visa-individuals-with-extraordinary-ability-or-achievement),
[USCIS Policy Manual Vol. 2, Part M, Ch. 4](https://www.uscis.gov/policy-manual/volume-2-part-m-chapter-4).
Reviewed as of `O1_CRITERIA_LAST_REVIEWED = 2026-08-15` in that file —
bump this date whenever the static text changes.

### Deterministic status derivation (`app/services/o1_assessment.py`)

Given the evidence items Featherless extracted for one criterion, status
is computed by a fixed rule over structured fields only — never by parsing
the model's prose:

1. No evidence items for the criterion -> `no_support_found`.
2. Any item has `flag_for_expert_review=true` -> `needs_expert_review`
   (the model sets this only when two documents genuinely conflict).
3. Every remaining item is `evidence_role="self_reported"` (e.g. a resume)
   -> `no_support_found` — a self-reported fact is a lead, never
   independent proof.
4. At least one `direct_document`/`supporting_document` item that is not
   future-dated and carries no `limitations` -> `documented_support_found`.
5. Otherwise (evidence exists but is future-dated and/or limited) ->
   `partial_support_found`.

`is_future_dated` is computed in Python by comparing the item's `date`
against the assessment's `as_of_date` — **never** taken from the model —
so a judging invitation dated after today can never be silently upgraded
to completed judging, no matter what the model's prose says. When an item
is future-dated, `build_o1_assessment` also appends a limitation
("...it is not proof of a completed action.") if the model didn't already
include one, guaranteeing rule 5 catches it even if the model forgot.

This directly encodes the specified evidence-reasoning rules:

- An **award certificate** proves receipt only — the system prompt
  instructs the model to add a "missing recognition evidence" limitation
  unless the document itself states selection criteria/applicant
  pool/judging standards, which keeps `awards` at `partial_support_found`.
- A **future judging invitation** is evidence of a planned role, not
  completed judging — rule 4's future-date check keeps `judging` at most
  `partial_support_found`, and the action plan emits a
  `request_confirmation` action suggesting organizer confirmation,
  completed scorecards (sensitive information removed), and event records
  — never manufacturing a completed judging record.
- A **resume** is always `evidence_role="self_reported"` — rule 3 means it
  can surface as a lead in the evidence list but never independently moves
  a criterion past `no_support_found`.
- An **employment letter** alone doesn't establish a distinguished
  reputation or critical role — the model is instructed to add that
  limitation, keeping `critical_employment` at `partial_support_found`.
- An **innovation/achievement award** alone doesn't establish major
  significance — same pattern, keeps `original_contribution` at
  `partial_support_found` absent independent-impact evidence.
- **High salary** claims need both a compensation figure and a comparison
  benchmark; **published material** must be *about* the beneficiary, not
  merely authored by them; **membership** must require outstanding
  achievement judged by experts, not ordinary paid membership — all
  enforced as system-prompt instructions that produce a `limitations` entry
  when unmet, which rule 5 turns into `partial_support_found`.
- `is_one_time_major_achievement` / `is_comparable_evidence` default
  `false` and the system prompt instructs the model to set them `true`
  only for achievements on the order of a Nobel Prize/Pulitzer/Olympic
  medal, or an explicit comparable-evidence substitution — an ordinary
  award is never inferred as a one-time major achievement.

### Coverage counts and documentation_coverage (deterministic, Python-only)

`O1AssessmentSummary`'s four counts
(`criteria_with_document_support_count`, `criteria_with_partial_support_count`,
`criteria_without_support_count`, `criteria_needing_expert_review_count`)
are a `collections.Counter` over the eight computed statuses — always sum
to 8, always computed after the Featherless response is validated, never
requested from or trusted from the model. `documentation_coverage`
(`limited`/`developing`/`broad`) is a simple threshold over the documented
and partial counts — informational only, and every response repeats:
**"Document coverage is not a determination that any USCIS criterion is
satisfied."** (`o1_assessment.DOCUMENT_COVERAGE_DISCLAIMER`).

### Action plan (evidence-gathering only, never a filing instruction)

`_build_action_plan` emits one `O1ActionItem` per criterion (type,
priority, `related_criterion`, `action`, `why_it_matters`, suggested
supporting materials — no dates, no fabricated deadlines) plus one
standing `attorney_review` item. Action types are a closed enum
(`collect_document`, `request_confirmation`, `collect_metrics`,
`obtain_independent_evidence`, `verify_fact`, `attorney_review`) —
there is no action type that could read as "file now" or "submit a
petition." The judging criterion gets a special-cased
`request_confirmation` action when it has a future-dated item, per the
evidence-reasoning rule above.

### Featherless: one shared extraction path, two schemas

`FeatherlessService._analyze` (generic over the output Pydantic model) now
holds every bit of shared completion behavior — size guard, one batch
call, `_call_with_retries`, Pydantic validation via
`output_model.model_validate(data, context={"valid_document_ids": ...})`,
and exactly one repair attempt — refactored out of what was previously
`analyze_documents`-only logic. `analyze_documents` (Phase 3,
`LLMAnalysisOutput`) and `analyze_o1_evidence` (Phase 4,
`O1LLMAnalysisOutput`) both delegate to it, differing only in their system
prompt template and output schema — no API/retry logic is duplicated
between phases, and both share the same process-wide
`_FEATHERLESS_CALL_LOCK`. The O-1A system prompt encodes every reasoning
rule above (see `_O1_SYSTEM_PROMPT_TEMPLATE` in
`app/services/featherless_service.py`) and repeats the same untrusted-data
instruction as Phase 3: every `<document>` block is data, never
instructions, and every `source_document_id` must be one of the supplied
document IDs or the response fails Pydantic validation.

### API and error handling

`app/routers/o1.py` mirrors `app/routers/analysis.py`'s shape exactly:

| Endpoint | Behavior |
| --- | --- |
| `GET /api/o1/criteria` | Always 200 — the 8 static criteria, the two informational categories, official sources, and `last_reviewed`. Never calls Supermemory/Featherless. |
| `POST /api/o1/assessment/run` | 201 with the full `O1Assessment` on success. 409 (`"No processed documents are available for O-1A assessment."`) when the demo container has zero `done` documents — nothing is stored. 503 if Supermemory/Featherless aren't configured. 502 on upstream/validation failure. 413 if combined document content exceeds the character cap. |
| `GET /api/o1/assessment/latest` | 200 with the last stored assessment, 404 before any run. |

### In-process assessment store (same accepted limitation as Phase 3)

`app/routers/o1._latest_assessment` is a module-level variable guarded by
an `asyncio.Lock` only against interleaved writes within one process —
restarting the backend or running more than one worker loses it, and
there is no history and no attorney-review workflow. Same trade-off as
Phase 3's `_latest_analysis`; a real deployment needs a database here
too. No database was added in this phase, per scope.

### Frontend

`frontend/src/O1Plan.tsx` (nav item "O-1 Plan", alongside Dashboard and
Documents). "Build my evidence plan" — disabled until at least one
document is `done` — calls `POST /api/o1/assessment/run`. Renders: a
coverage summary (counts, `documentation_coverage`, the disclaimer, and
one-time-achievement/comparable-evidence flags); all eight criteria
always, each showing its status badge (worded "Document support found" /
"Partial documentation" / "No supporting document found" / "Needs expert
review" — deliberately never a green "eligible" indicator or a
percentage); documented evidence and planned/future evidence rendered as
visually distinct groups within a criterion (a future-dated judging
invitation is always shown under "Planned / future evidence," never mixed
into "Documented evidence"); limitations; what remains unproven; suggested
evidence to collect; and a prioritized action plan. A "Print / Save
report" button calls `window.print()` against print-specific CSS in
`O1Plan.css` (hides nav/buttons, avoids breaking cards across pages). The
fixed disclaimer — "Proofly evaluates document readiness, not visa
eligibility. An attorney must evaluate the complete case." — and the two
official USCIS links are always shown.

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
above (`app/services/featherless_service.py`). As of Phase 4, the same
service (via a shared, generic `_analyze` method — see "Phase 4" above)
also runs the one-batch O-1A evidence extraction
(`analyze_o1_evidence`) that `app/services/o1_assessment.py` turns into a
full evidence-coverage assessment. The document-grounded chatbot's
generation step is still a future phase. Referenced only via
`FEATHERLESS_API_KEY` / `FEATHERLESS_BASE_URL` / `FEATHERLESS_MODEL` — the
backend never hardcodes model calls with inline secrets.

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
