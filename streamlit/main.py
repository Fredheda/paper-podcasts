import sys
import logging
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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


def main():
    """Run the partial pipeline example."""
    _ = load_dotenv()
    anthropic_api_key = os.getenv('anthropic_api_key')
    openai_api_key = os.getenv("OPENAI_API_KEY")

    arxiv_service = ArxivService()
    pdf_service = PdfService()
    llm_provider = AnthropicProvider(api_key=anthropic_api_key)
    llm_service = LLMService(provider=llm_provider, prompts_dir=str(REPO_ROOT / "prompts"))
    tts_provider = OpenAITTSProvider(api_key=openai_api_key)
    audio_service = AudioService(provider=tts_provider)

    pipeline = PaperPipeline(
        arxiv_service=arxiv_service,
        pdf_service=pdf_service,
        llm_service=llm_service,
        audio_service=audio_service,
        storage_dir=REPO_ROOT / "data",
    )

    papers = arxiv_service.search_by_topic("attention is all you need", max_results=1, exact=True)
    paper = papers[0]

    _ = pipeline.process_paper(paper)

if __name__ == "__main__":
    main()
