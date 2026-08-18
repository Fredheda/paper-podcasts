# Frontend

React + TypeScript + Tailwind UI for Paper Podcasts.

## Setup

```bash
cd frontend
npm install
```

## Development

```bash
npm run dev
```

Current Vite config:

- Host: `localhost` (not `127.0.0.1` — bound to the hostname specifically)
- Port: `5173`
- Browser auto-open: enabled
- `server.proxy` forwards `/api` and `/health` to `http://localhost:8000`
  (the backend) — see "API Base URL" below for why.

## Build

```bash
npm run build
npm run preview
```

## API Base URL

Defaults to `''` (relative paths, same-origin) — there is no CORS setup
anywhere in this app, in prod or local dev, because the browser never talks
to the backend directly in either case. In prod, `server.js` proxies `/api/*`
and `/health` server-side; in local dev, `vite.config.ts`'s `server.proxy`
does the same for the Vite dev server. See `backend/README.md`'s "No CORS
middleware" note for the full explanation.

`VITE_API_BASE_URL` only needs setting if the backend ever lives on a
genuinely different origin than whatever's serving this frontend — not the
case today.

Do not place backend secrets in frontend environment variables.

## Feature Coverage

- Search papers and multi-select enqueue
- Queue monitor with live stage/progress updates
- Library filters by processing status and listen status
- Listen/unlisten toggles
- Audio playback from backend stream endpoint
- Rich summary rendering (HTML/Markdown/mixed), auto-fetched per paper as it
  appears in the library — no separate "view" step, no Abstract tab, no
  full-text modal. Reading the paper itself happens via "Open on arXiv".
- Background polling (`/api/jobs`, `/api/library`) pauses after 60s with no
  active/queued job, and resumes on tab focus or on search/enqueue — lets
  both backend container apps actually reach their scale-to-zero cooldown
  while a tab stays open.
