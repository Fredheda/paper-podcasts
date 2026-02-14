# Streamlit (Legacy UI)

This folder contains the preserved Streamlit interface. The primary app is now the `backend/` + `frontend/` stack, but this UI remains available.

## Run

From repo root:

```bash
pip install -r streamlit/requirements.txt
streamlit run streamlit/app.py
```

Required environment variables in root `.env`:

```bash
ANTHROPIC_API_KEY=your_key
OPENAI_API_KEY=your_key
```

## What It Uses

- Shared pipeline/services in `src/`
- Shared prompts in `prompts/`
- Shared artifact storage in `data/`

## Streamlit Capabilities

- Search arXiv papers
- Queue papers for background processing
- Track processing status
- Browse processed library entries
- Read summaries and extracted text previews
- Play generated audio and track listened state

## Notes

- This implementation is kept for compatibility and comparison.
- New UX and active iteration are in `frontend/` with API endpoints in `backend/`.
