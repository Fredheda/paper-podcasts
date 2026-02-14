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

- Host: `127.0.0.1` (local machine only)
- Port: `5173`
- Browser auto-open: enabled

## Build

```bash
npm run build
npm run preview
```

## API Base URL

Defaults to `http://localhost:8000`.

Override with:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

Do not place backend secrets in frontend environment variables.

## Feature Coverage

- Search papers and multi-select enqueue
- Queue monitor with live stage/progress updates
- Library filters by processing status and listen status
- Listen/unlisten toggles
- Audio playback from backend stream endpoint
- Abstract view, rich summary rendering (HTML/Markdown/mixed), full-text modal reader
