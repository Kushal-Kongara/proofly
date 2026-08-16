# Proofly

Proofly is an AI immigration document and O-1 evidence copilot built for Open Atlas 2026.

**Informational support only — not legal advice.** See `docs/PRODUCT_SPEC.md`.

## Hackathon Scope

- Immigration document vault
- Visa/status compliance timeline
- Document-grounded chatbot
- O-1A evidence-readiness planner

All demo data is synthetic (`sample_documents/demo_profile.json`). No authentication in this build.

## Technology

- React + TypeScript + Vite (frontend)
- FastAPI + Pydantic (backend)
- Supermemory (document vault ingestion, Phase 2) — Featherless, Tavily still future integrations

See `docs/ARCHITECTURE.md` for how these fit together.

## Local Setup

### 1. Environment variables

```bash
cp .env.example .env
```

Fill in real values in `.env` (never commit it — it's gitignored). To use the
document vault, set `SUPERMEMORY_API_KEY` to a real Supermemory API key.
`SUPERMEMORY_CONTAINER_TAG` defaults to `proofly_demo_maya` — the backend is
the only thing that sets this; the frontend never sends a container tag.

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

## Project Layout

```
backend/              FastAPI app, Pydantic schemas, Supermemory service, tests
frontend/              React + TypeScript + Vite app (incl. Document Vault page)
docs/                   Product spec and architecture docs
sample_documents/       Synthetic demo data (Maya Patel, fictional) + generated demo PDFs
scripts/                Synthetic PDF generator
```
