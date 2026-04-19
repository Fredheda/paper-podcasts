"""Application service lifecycle and shared runtime state.

Why this exists:
- FastAPI route handlers should not build heavyweight services per request.
- We initialize services once at startup and expose them through a tiny state object.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import HTTPException

from .config import DATA_DIR, DEFAULT_MAX_CONCURRENT, PROMPTS_DIR
from src.pipeline.paper_pipeline import PaperPipeline
from src.services.arxiv_service import ArxivService
from src.services.audio_service import AudioService
from src.services.llm_providers import AnthropicProvider
from src.services.llm_service import LLMService
from src.services.pdf_service import PdfService
from src.services.processing_manager import ProcessingManager
from src.services.tts_providers import OpenAITTSProvider

logger = logging.getLogger(__name__)


class AppState:
    """Holds long-lived services for the app process."""

    def __init__(self) -> None:
        self.arxiv: Optional[ArxivService] = None
        self.pipeline: Optional[PaperPipeline] = None
        self.processing: Optional[ProcessingManager] = None
        self.llm_provider: Optional[AnthropicProvider] = None


state = AppState()


def require_state() -> tuple[ArxivService, ProcessingManager]:
    """Guard helper for routes that need initialized services."""
    if state.arxiv is None or state.processing is None:
        raise HTTPException(status_code=503, detail="Backend services are not initialized")
    return state.arxiv, state.processing


@asynccontextmanager
async def lifespan(_: object):
    """Build all shared services once on startup and tear down on shutdown."""
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    # Fail startup early if required secrets are missing.
    if not anthropic_api_key or not openai_api_key:
        raise RuntimeError("Missing API keys. Set ANTHROPIC_API_KEY and OPENAI_API_KEY.")

    arxiv_service = ArxivService()
    pdf_service = PdfService()
    llm_provider = AnthropicProvider(api_key=anthropic_api_key)
    llm_service = LLMService(provider=llm_provider, prompts_dir=str(PROMPTS_DIR))
    tts_provider = OpenAITTSProvider(api_key=openai_api_key)
    audio_service = AudioService(provider=tts_provider)

    pipeline = PaperPipeline(
        arxiv_service=arxiv_service,
        pdf_service=pdf_service,
        llm_service=llm_service,
        audio_service=audio_service,
        storage_dir=DATA_DIR,
    )

    state.arxiv = arxiv_service
    state.pipeline = pipeline
    state.processing = ProcessingManager(pipeline, max_concurrent=DEFAULT_MAX_CONCURRENT)
    state.llm_provider = llm_provider

    logger.info("Backend initialized with data dir: %s", DATA_DIR)

    try:
        yield
    finally:
        if state.processing:
            state.processing.shutdown()

