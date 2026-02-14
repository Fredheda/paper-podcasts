# Paper Podcasts

Paper Podcasts turns arXiv papers into summaries and audio, with a shared processing pipeline and two UI options:

- `streamlit/`: legacy Streamlit app (preserved)
- `backend/` + `frontend/`: current FastAPI + React app

## Repository Layout

- `src/`: shared domain models, services, and pipeline
- `prompts/`: shared LLM prompts
- `data/`: generated paper artifacts (state, extracted text, summaries, audio)
- `assets/`: static images/diagrams
- `backend/`: FastAPI API server
- `frontend/`: React + TypeScript + Tailwind UI
- `streamlit/`: legacy Streamlit implementation

## Prerequisites

- Python 3.11+
- Node.js 18+
- API keys:
  - `ANTHROPIC_API_KEY`
  - `OPENAI_API_KEY`

Create a root `.env` file:

```bash
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
```

## Run (Current App: Backend + Frontend)

1. Start backend:

```bash
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8000
```

2. Start frontend (new terminal):

```bash
cd frontend
npm install
npm run dev
```

Frontend runs on `http://127.0.0.1:5173` and calls backend at `http://localhost:8000` by default.

## Run (Legacy Streamlit App)

```bash
pip install -r streamlit/requirements.txt
streamlit run streamlit/app.py
```

## Core Capabilities

- Search papers on arXiv
- Enqueue processing jobs with concurrent workers (up to configured limit) and queue overflow
- Track live job status/progress
- Browse processed library with filters
- View abstract, summary, and extracted full text
- Play generated audio and mark listened/unlistened

## Notes

- Artifacts are written under `data/` and shared across Streamlit and API/UI.
- Backend security controls (CORS allowlist, optional API key, rate limiting, HTTPS controls) are documented in `backend/README.md`.
