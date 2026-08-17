# Proofly

Proofly is an AI immigration document and O-1 evidence copilot built for Open Atlas 2026.

**Informational support only — not legal advice.** See `docs/PRODUCT_SPEC.md`.

## Hackathon Scope

- Immigration document vault
- Visa/status compliance timeline
- Document-grounded chatbot
- O-1A evidence-readiness planner
- Official immigration updates search (Tavily, official government sources only)

All demo data is synthetic (`sample_documents/demo_profile.json`). No authentication in this build.

## Technology

- React + TypeScript + Vite (frontend)
- FastAPI + Pydantic (backend)
- Supermemory (document vault ingestion, Phase 2; document-mode semantic
  search, Phase 5), Featherless (document extraction + deterministic
  timeline, Phase 3; O-1A evidence extraction, Phase 4; document-grounded
  chat answers, Phase 5), Tavily (official government immigration source
  search, Phase 6)

See `docs/ARCHITECTURE.md` for how these fit together.

## Local Setup

### 1. Environment variables

```bash
cp .env.example .env
```

Fill in real values in `.env` (never commit it — it's gitignored). To use the
document vault, set `SUPERMEMORY_API_KEY` to a real Supermemory API key.
`SUPERMEMORY_CONTAINER_TAG` defaults to `proofly_demo_maya` — the backend is
the only thing that sets this; the frontend never sends a container tag. To
run document analysis, also set `FEATHERLESS_API_KEY`
(`FEATHERLESS_BASE_URL` and `FEATHERLESS_MODEL` already have sane defaults).
To use Official Updates, also set `TAVILY_API_KEY`.

### 2. Backend (FastAPI)

Requires Python 3.12+ (3.13 also works; avoid 3.14 until dependency wheels catch up).

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Backend runs at http://localhost:8000. Health check: http://localhost:8000/health

Run backend tests (Supermemory is always mocked — no API key or network
access needed, and no credits are consumed):

```bash
cd backend
source .venv/bin/activate
pytest
```

### 3. Frontend (React + Vite)

Requires Node 20+.

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend runs at http://localhost:5173 and expects the backend at the URL in `VITE_API_BASE_URL` (default `http://localhost:8000`).

Type-check / production build:

```bash
cd frontend
npm run build
```

### 4. Document Vault (synthetic demo PDFs + Supermemory upload)

Seven fictional PDFs (I-20/I-94/EAD summaries, resume, employment letter,
award, judging invitation — all for the fictional "Maya Patel") are already
generated under `sample_documents/pdfs/`. To regenerate them:

```bash
cd backend
source .venv/bin/activate
pip install -r ../scripts/requirements.txt
python ../scripts/generate_synthetic_pdfs.py
```

With the backend and frontend both running and `SUPERMEMORY_API_KEY` set,
open http://localhost:5173, drag one or more files from
`sample_documents/pdfs/` onto the Document Vault dropzone (or use the file
picker), and watch the processing status update until it reaches "Ready".
Accepted types: PDF, PNG, JPG, JPEG, up to 10 MB each.

To run a one-shot live Supermemory smoke test (uploads exactly one
synthetic PDF, polls until done/failed, prints the resulting document ID —
never the API key):

```bash
cd backend
source .venv/bin/activate
python scripts/live_smoke_test.py
```

### 5. Document Analysis (Featherless extraction + deterministic timeline)

Once at least one document in the vault has reached "Ready" (`done`), open
the **Dashboard** tab and click **Analyze documents**. This makes one batch
call to Featherless over every completed document in the demo container,
validates the structured result, and computes a deterministic timeline in
Python (no dates or "days remaining" are ever computed by the model — see
`docs/ARCHITECTURE.md`).

Equivalent API calls:

```bash
curl -X POST http://localhost:8000/api/analysis/run   # runs analysis, returns the result (409 if no documents are done yet)
curl http://localhost:8000/api/analysis/latest         # most recent result (404 if none yet)
curl http://localhost:8000/api/timeline                # just the timeline (404 if none yet)
```

The latest analysis result lives in an in-process variable — restarting the
backend, or running more than one worker process, loses it. That's an
accepted limitation for this prototype; see `docs/ARCHITECTURE.md`.

### 6. O-1A Evidence Readiness Planner (Phase 4)

**Proofly organizes evidence and identifies gaps — it never predicts
approval, computes an eligibility percentage, or states that a USCIS
criterion is legally satisfied.** Only an immigration attorney can make
that determination. See "Evidence coverage vs. legal eligibility" below.

Open the **O-1 Plan** tab and click **Build my evidence plan**. This makes
one batch Featherless call over every completed document in the demo
container, validates the structured result, and deterministically (in
Python, never the model) maps evidence onto the eight static O-1A criteria,
computes document-coverage counts, and generates a prioritized
evidence-gathering action plan. Use **Print / Save report** for a
print-friendly copy.

Equivalent API calls:

```bash
curl http://localhost:8000/api/o1/criteria                # the 8 static criteria + official USCIS links
curl -X POST http://localhost:8000/api/o1/assessment/run  # runs the assessment (409 if no documents are done yet)
curl http://localhost:8000/api/o1/assessment/latest        # most recent assessment (404 if none yet)
```

The static criteria (`backend/app/data/o1_criteria.py`) are sourced from:

- https://www.uscis.gov/working-in-the-united-states/temporary-workers/o-1-visa-individuals-with-extraordinary-ability-or-achievement
- https://www.uscis.gov/policy-manual/volume-2-part-m-chapter-4

Last reviewed **2026-08-15** (`O1_CRITERIA_LAST_REVIEWED` in that file) —
update this date whenever the static text is edited.

#### Evidence coverage vs. legal eligibility

A criterion status of `documented_support_found` means *a document was
found that plainly speaks to that criterion* — it is document coverage,
not a legal conclusion. Every criterion assessment carries
`requires_attorney_review: true`, and every response includes the fixed
disclaimer: **"Document coverage is not a determination that any USCIS
criterion is satisfied."** Status values are deliberately never
`eligible`/`ineligible`/`approved`/`denied`/`criterion_satisfied`, and no
API response ever contains a percentage, probability, or approval-chance
figure — see `docs/ARCHITECTURE.md` for the full reasoning rules.

Like the Phase 3 analysis store, the latest O-1A assessment lives in an
in-process variable only — restarting the backend, or running more than
one worker, loses it, and there is no attorney-review workflow. Same
accepted prototype limitation as Phase 3.

To run a one-shot live smoke test (uploads only the synthetic PDFs not
already in the container, waits for processing, then makes exactly one
live Featherless O-1A call and prints a coverage report — never raw
document text or API keys):

```bash
cd backend
source .venv/bin/activate
python scripts/live_o1_smoke_test.py
```

### 7. Ask Proofly (document-grounded RAG chatbot, Phase 5)

**This is document Q&A, not general immigration advice.** Proofly answers
only from your own uploaded documents — see "Why chat history is never
saved as evidence" in `docs/ARCHITECTURE.md` for the full grounding and
citation-enforcement rules.

Open the **Ask Proofly** tab and ask a question (Enter to send, Shift+Enter
for a newline). Each question runs Supermemory document-mode semantic
search over the demo container, hands the retrieved chunks to one
Featherless answer call, and validates that every citation in the response
actually points at a retrieved chunk before returning it. Grounded answers
show expandable **Sources** cards (filename, page when known, a short
excerpt); when nothing relevant is found, Proofly says so directly rather
than guessing. Conversation history lives only in the browser tab — it's
never sent to Supermemory and is lost on refresh (see "Browser-only chat
history" below).

Equivalent API call:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "When does my current work authorization expire?", "history": []}'
```

### 8. Official Updates (Tavily-powered official immigration source search, Phase 6)

**This is a link/snippet search over official government sources, not
personalized legal advice.** Proofly never claims a search result changes
your case, never converts a search snippet into legal advice, and never
labels a result "urgent" based only on search relevance — see "Why Tavily
is restricted to official domains" in `docs/ARCHITECTURE.md`.

Open the **Official Updates** tab, pick a category (F-1 / OPT, O-1A, or
General USCIS) and a time range (past month or past year). Each combination
calls Tavily once, restricted to a fixed, server-owned allowlist of official
domains (`uscis.gov`, `dhs.gov`, `studyinthestates.dhs.gov`, `ice.gov`,
`travel.state.gov`, `cbp.gov`, `federalregister.gov`), and is cached
in-process for 15 minutes so repeat views don't spend another Tavily
credit.

Equivalent API call:

```bash
curl "http://localhost:8000/api/updates?category=f1_opt&time_range=year"
```

The in-memory cache (keyed by category + time range) is not shared across
worker processes and is lost on restart — same accepted prototype
limitation as the Phase 3/4 in-process stores.

## Deployment

Render Blueprint at `render.yaml` (repo root) deploys `proofly-api`
(FastAPI backend) and `proofly-web` (static frontend build) as two
services. See `docs/DEPLOYMENT.md` for the full runbook — Blueprint steps,
exact environment-variable names, `CORS_ORIGINS` format, smoke-test and
pre-demo checklists, rollback, and why the backend must stay at one worker.

## Project Layout

```
backend/              FastAPI app, Pydantic schemas, Supermemory + Featherless services, tests
frontend/              React + TypeScript + Vite app (Dashboard + Document Vault pages)
docs/                   Product spec, architecture, and deployment docs
sample_documents/       Synthetic demo data (Maya Patel, fictional) + generated demo PDFs
scripts/                Synthetic PDF generator
render.yaml             Render Blueprint (backend + frontend services)
```
