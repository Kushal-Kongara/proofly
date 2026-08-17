# Deployment (Render, Phase 7A)

Proofly deploys as two Render services from one Blueprint (`render.yaml` at
the repo root): `proofly-api` (FastAPI backend) and `proofly-web` (static
React/Vite frontend). This document is the deploy runbook. It never
contains a secret value — only variable **names**, same rule as
`docs/ARCHITECTURE.md`'s Security section and `.env.example`.

## 1. Blueprint deployment steps

1. Push this repo (with `render.yaml` at the root) to GitHub.
2. In the Render dashboard: **New > Blueprint**, connect the repo, and let
   Render parse `render.yaml`. It will propose both services
   (`proofly-api`, `proofly-web`).
3. Before the first deploy, Render will prompt for every `sync: false`
   environment variable it found (see the exact list below). Fill them in
   — this is the only place secret values are ever entered.
4. Apply the Blueprint. Render builds and deploys both services.
5. Once `proofly-api` has a live URL, set `proofly-web`'s
   `VITE_API_BASE_URL` to it (see step 3 below) and redeploy
   `proofly-web` — the frontend is a static build, so the backend URL is
   baked in at build time, not read at runtime.
6. Once `proofly-web` has a live URL, set `proofly-api`'s `CORS_ORIGINS`
   to it (see the CORS section below) and redeploy `proofly-api`.

Steps 5 and 6 are circular on a first deploy (each service's config needs
the other's URL) — expect one deploy of each service, then one redeploy of
each once both URLs are known. This is normal, not a failure.

## 2. Environment variables (names only — never values)

### `proofly-api` (backend)

| Variable | Set by | Notes |
|---|---|---|
| `PYTHON_VERSION` | Blueprint (`render.yaml`) | Pinned to `3.13.8` — see "Why Python 3.13.8" below. |
| `APP_ENV` | Blueprint (`render.yaml`) | `production`. |
| `FEATHERLESS_BASE_URL` | Blueprint (`render.yaml`) | Non-secret default; override only if the Featherless endpoint changes. |
| `FEATHERLESS_MODEL` | Blueprint (`render.yaml`) | Non-secret default; override only if the demo switches models. |
| `SUPERMEMORY_CONTAINER_TAG` | Blueprint (`render.yaml`) | Non-secret default; the server-owned demo container tag. |
| `FEATHERLESS_API_KEY` | You, in the Render dashboard | Secret. Never committed, never copied from local `.env`. |
| `SUPERMEMORY_API_KEY` | You, in the Render dashboard | Secret. Same rule. |
| `TAVILY_API_KEY` | You, in the Render dashboard | Secret. Same rule. |
| `CORS_ORIGINS` | You, in the Render dashboard | Not secret, but deployment-specific — the deployed frontend's exact origin. Format below. |

`PORT` is never set manually — Render injects it, and `startCommand` reads
it as `$PORT`.

### `proofly-web` (frontend)

| Variable | Set by | Notes |
|---|---|---|
| `VITE_API_BASE_URL` | You, in the Render dashboard | The deployed `proofly-api` URL. No backend API keys ever belong here — the frontend never talks to Featherless/Supermemory/Tavily directly (see `docs/ARCHITECTURE.md`'s Overview). |

## 3. Setting the final frontend and backend URLs

- **Backend URL** (`VITE_API_BASE_URL`, on `proofly-web`): the full HTTPS
  URL Render assigns `proofly-api` (e.g. its `onrender.com` URL, or a
  custom domain if one is attached), with **no trailing slash** —
  `frontend/src/api/client.ts` concatenates it directly with each request
  path (`${API_BASE_URL}/api/...`).
- **Frontend URL** (`CORS_ORIGINS`, on `proofly-api`): the full HTTPS URL
  Render assigns `proofly-web` (or its custom domain), in the format below.
- Because `proofly-web` is a static build, `VITE_API_BASE_URL` is baked in
  at `vite build` time — changing it always requires a redeploy of
  `proofly-web`, not just an environment variable update.

### `CORS_ORIGINS` format (`app/config.py`'s parser)

`Settings.cors_origin_list` splits the raw `CORS_ORIGINS` string on commas
and strips whitespace from each entry:

```
CORS_ORIGINS=https://proofly-web.onrender.com
```

Multiple origins (e.g. a custom domain alongside the default `onrender.com`
one):

```
CORS_ORIGINS=https://proofly-web.onrender.com,https://proofly.example.com
```

**Never set `CORS_ORIGINS` to `*`.** The parser passes each entry straight
to `CORSMiddleware`'s `allow_origins`, which is configured with
`allow_credentials=True` (`app/main.py`) — browsers reject a wildcard
`Access-Control-Allow-Origin` on a credentialed request outright, so a `*`
here would silently break every real request from the deployed frontend
rather than "working but insecurely." It's also exactly the "no explicit
origin" failure mode this phase closes off. Always list the deployed
frontend origin(s) explicitly.

## 4. Why the backend runs one worker

`startCommand` is fixed at `--workers 1`. This is not a cost-tier
default — it's required correctness for the current build. Three pieces of
state are in-process Python variables, not a database or shared cache:

- Phase 3's `_latest_analysis` (`app/routers/analysis.py`)
- Phase 4's `_latest_assessment` (`app/routers/o1.py`)
- Phase 6's updates cache (`app/services/tavily_service.py`)

A second worker process would hold its own independent copy of each — a
request handled by worker A could silently fail to see an assessment just
run by worker B. See `docs/ARCHITECTURE.md`'s "In-process ... store
(accepted limitation)" sections (Phase 3, Phase 4, Phase 6) for the full
reasoning. This also means Render's autoscaling (multiple instances) is not
safe for this build — `numInstances: 1` in `render.yaml` is deliberate,
same reasoning.

## 5. In-memory state limitations (carries over to production)

- The latest document analysis, the latest O-1A assessment, and the
  cached official-updates results all live only in the running backend
  process's memory.
- **A backend restart or redeploy loses all of them.** After any deploy of
  `proofly-api` (including an env var change, which Render redeploys for),
  re-run document analysis and the O-1A assessment before judging/demoing.
- Chat conversation history is browser-only (never sent to Supermemory) —
  a page refresh loses it, deploy or not. This is unrelated to the backend
  restart issue above and was already true in local dev.

## 6. Instance recommendation for judging

Use the Render **Starter** plan for both services during judging (already
`render.yaml`'s default `plan: starter` on `proofly-api`; `proofly-web` is
a static site with no compute plan). Starter avoids the free-tier's
spin-down-after-idle behavior — see the warm-up checklist below for why a
cold start during a live judging session is the specific failure mode to
avoid. There's no in-memory-state reason to go beyond Starter — the
single-worker constraint above already caps this build at one process
regardless of instance size.

## 7. Deployment smoke-test checklist

Run through this once after every fresh deploy, before telling anyone the
environment is live:

- [ ] `GET https://<proofly-api-url>/health` returns `{"status":"ok","service":"proofly-api"}`.
- [ ] Open `https://<proofly-web-url>` — the header's "Backend status" reads
      **connected** (confirms `VITE_API_BASE_URL` and `CORS_ORIGINS` are
      both correct — a CORS misconfiguration shows as **disconnected**
      here, not a console-only error).
- [ ] Upload one synthetic PDF from `sample_documents/pdfs/` via the
      Document Vault tab; confirm it reaches "Ready".
- [ ] Dashboard tab → **Analyze documents** succeeds (one real Featherless
      call).
- [ ] O-1 Plan tab → **Build my evidence plan** succeeds (one real
      Featherless call) and shows all 8 criteria.
- [ ] Ask Proofly tab → ask one question about an uploaded document; confirm
      a grounded answer with a Sources citation.
- [ ] Official Updates tab → pick any category/time range; confirm results
      load (one real Tavily call).
- [ ] Confirm no API key or raw prompt appears anywhere in the browser
      network tab response bodies.

## 8. Pre-demo warm-up checklist

Run this 5–10 minutes before a live demo/judging session, in order:

1. Hit `/health` once to confirm the backend is up and not cold-starting.
2. Upload the synthetic demo PDFs (`sample_documents/pdfs/`) if the vault
   is empty (a redeploy since the last demo wipes in-memory-adjacent state
   only if Supermemory's own container was also cleared — the vault itself
   is Supermemory-backed and persists across backend restarts; only the
   *analysis/assessment/cache* are in-process and need re-running per
   Section 5).
3. Re-run **Analyze documents** (Dashboard tab) — populates the in-process
   analysis store lost on the last deploy.
4. Re-run **Build my evidence plan** (O-1 Plan tab) — populates the
   in-process O-1A assessment store lost on the last deploy.
5. Ask one warm-up question in Ask Proofly — this is also the first real
   Featherless call on a cold model and is where "cold-model demo risk"
   (see `docs/ARCHITECTURE.md`, Phase 5) is most visible; don't let the
   first live question in front of judges be the first call of the day.
6. Load Official Updates once per category you plan to demo — the first
   load per category/time-range pair is a live Tavily call; the 15-minute
   cache only helps for repeats after this.

## 9. Rollback procedure

Render keeps prior deploys per service.

1. Render dashboard → the affected service (`proofly-api` or
   `proofly-web`) → **Deploys**.
2. Find the last known-good deploy → **Rollback to this deploy** (or
   redeploy that specific commit).
3. Roll back `proofly-api` and `proofly-web` independently — they're
   separate services with separate deploy histories; a bad backend deploy
   does not require rolling back the frontend, and vice versa.
4. After any backend rollback, re-run the Section 5/8 warm-up steps — a
   rollback is still a process restart, so the in-process stores are empty
   again.
5. If the regression is already merged to the deployed branch, also revert
   the commit in git so the next auto-deploy (triggered by the next push)
   doesn't reintroduce it — a dashboard rollback alone doesn't change what
   `autoDeployTrigger: commit` will deploy next time.

## 10. Demo data only

**Only upload the synthetic demo documents under `sample_documents/pdfs/`
(the fictional "Maya Patel" profile) to any deployed environment.** This
build has no authentication and no per-user data isolation — everything
uploaded goes into one server-controlled Supermemory container
(`SUPERMEMORY_CONTAINER_TAG`) shared by every visitor to the deployed URL.
Never upload a real person's real immigration documents to a Render
deployment of this project.

## Appendix: why Python 3.13.8

`render.yaml` pins `PYTHON_VERSION=3.13.8` — the exact version
`backend/.venv` is built and tested against in this repo, and a 3.13.x
release (not 3.14, where some pinned wheels in `backend/requirements.txt`
aren't yet available — see `README.md`'s Local Setup section).
