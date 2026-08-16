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
- Supermemory, Featherless, Tavily (future integrations)

See `docs/ARCHITECTURE.md` for how these fit together.

## Local Setup

### 1. Environment variables

```bash
cp .env.example .env
```

Fill in real values in `.env` (never commit it — it's gitignored).

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

Run backend tests:

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

## Project Layout

```
backend/            FastAPI app, Pydantic schemas, tests
frontend/            React + TypeScript + Vite app
docs/                 Product spec and architecture docs
sample_documents/     Synthetic demo data (Maya Patel, fictional)
```
