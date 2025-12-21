"""
Partial Pipeline Processing Example

Demonstrates running pipeline stages independently and resuming across runs.
State is automatically persisted to disk after each stage.

Prerequisites:
- ANTHROPIC_API_KEY and OPENAI_API_KEY environment variables
- Internet connection for arXiv API
"""

import sys
import logging
from pathlib import Path

# Add project root to path so we can import src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

from src.services.arxiv_service import ArxivService
from src.services.pdf_service import PdfService
from src.services.llm_service import LLMService
from src.services.llm_providers import AnthropicProvider
from src.services.audio_service import AudioService
from src.services.tts_providers import OpenAITTSProvider
from src.pipeline import PaperPipeline
from dotenv import load_dotenv
import os


def main():
    """Run the partial pipeline example."""

    print("\n" + "=" * 70)
    print("Partial Pipeline Example")
    print("=" * 70)

    _ = load_dotenv()
    anthropic_api_key = os.getenv('anthropic_api_key')
    openai_api_key = os.getenv("OPENAI_API_KEY")

    arxiv_service = ArxivService()
    pdf_service = PdfService()
    llm_provider = AnthropicProvider(api_key=anthropic_api_key)
    llm_service = LLMService(provider=llm_provider, prompts_dir="../prompts")
    tts_provider = OpenAITTSProvider(api_key=openai_api_key)
    audio_service = AudioService(provider=tts_provider)

    pipeline = PaperPipeline(
        arxiv_service=arxiv_service,
        pdf_service=pdf_service,
        llm_service=llm_service,
        audio_service=audio_service,
        storage_dir=Path("data"),
    )

    papers = arxiv_service.search_by_topic("attention is all you need", max_results=1, exact=True)
    paper = papers[0]

    print(f"\n[Part 1] Download and Extract only")
    result = pipeline.process_paper(paper, stages=["download", "extract"])
    print(f"   State: {result.current_stage}")

    # Simulate script restart: delete and reload from disk
    print(f"\n[Part 2] Simulating script restart (load from disk)")
    paper_id = paper.arxiv_id
    del paper

    paper = pipeline.load_paper(paper_id)
    if not paper:
        print("   ✗ Failed to load paper")
        return

    print(f"   Loaded from disk - State: {paper.status}")

    # Resume with summarization
    result = pipeline.process_paper(paper, stages=["summarize"])
    print(f"   State: {result.current_stage}")

    # Complete with audio generation
    print(f"\n[Part 3] Audio generation")
    result = pipeline.process_paper(paper, stages=["audio"])
    print(f"   State: {result.current_stage}")

    print(f"\n✓ Pipeline complete - State file: data/papers/{paper.arxiv_id}/paper_state.json")

if __name__ == "__main__":
    main()
