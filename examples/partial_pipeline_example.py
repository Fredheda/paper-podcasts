"""
Example: Partial Pipeline Processing

This example demonstrates how to run only specific stages of the pipeline.
This is useful when you want to:
- Download papers now, summarize later
- Process stages incrementally (e.g., download 100 papers, then extract in batch)
- Resume processing from a specific stage
- Skip expensive operations (e.g., just download and extract, skip LLM)

Key concepts demonstrated:
- Specifying which stages to run
- State machine allows resuming from any stage
- Each stage can be run independently
- Results are preserved between runs

Prerequisites:
- ANTHROPIC_API_KEY environment variable set (only for summarize stage)
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
    print("Example 2: Partial Pipeline (Download + Extract Only)")
    print("=" * 70)

    # -------------------------------------------------------------------------
    # Setup: Initialize services and pipeline (same as Example 1)
    # -------------------------------------------------------------------------

    print("\n[Setup] Initializing services and pipeline...")

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

    # Get a paper to process
    papers = arxiv_service.search_by_topic("attention is all you need", max_results=1, exact=True)
    paper = papers[0]

    print(f"   ✓ Found paper: {paper.title[:60]}...")

    # -------------------------------------------------------------------------
    # Part 1: Run only download and extract stages
    # -------------------------------------------------------------------------
    # By specifying stages=["download", "extract"], we skip the summarize stage
    # This is useful if you want to:
    # - Download many papers quickly without expensive LLM calls
    # - Process them later in batch
    # - Check the extracted content before summarizing
    # - Save on API costs by only summarizing papers you actually need

    print("\n[Part 1] Running DOWNLOAD and EXTRACT stages only...")
    print("         (Skipping summarization to save time/cost)")

    # The state machine will:
    # 1. new → downloading → downloaded
    # 2. downloaded → extracting → extracted
    # 3. Stop at "extracted" state (not "completed")
    result = pipeline.process_paper(
        paper,
        stages=["download", "extract"]  # Only these two stages
    )

    print(f"\n   Current state: {result.current_stage}")
    print(f"   Expected state: extracted (not completed)")

    # We have download and extraction results, but no summary
    if result.download:
        print(f"\n   ✓ Downloaded:")
        print(f"     PDF: {result.download.pdf_path}")

    if result.extraction:
        print(f"\n   ✓ Extracted:")
        print(f"     Markdown: {result.extraction.saved_path}")
        print(f"     Characters: {result.extraction.character_count:,}")

    if result.summary:
        print(f"\n   ✗ Summary: None (as expected)")
    else:
        print(f"\n   ✓ No summary generated (we didn't request it)")

    # -------------------------------------------------------------------------
    # Part 2: Later, resume and complete the summarization stage
    # -------------------------------------------------------------------------
    # The state machine remembers where we left off
    # The paper's status field is now "extracted"
    # We can resume by running just the "summarize" stage
    #
    # This is powerful because:
    # - We don't re-download or re-extract (idempotent)
    # - We can resume days or weeks later
    # - We can process in batches (download 100, extract 100, summarize 10)


    print("\n[Part 2] Resuming to complete SUMMARIZATION stage...")
    print("         (Paper already downloaded and extracted, starting from current state)")

    # Check the paper's current state before resuming
    print(f"\n   Paper status before resume: {paper.status}")
    print(f"   State machine will validate we can transition: extracted → summarizing")

    # Run just the summarize stage
    # The state machine will:
    # 1. Verify we're in "extracted" state
    # 2. Transition: extracted → summarizing → summarized
    result = pipeline.process_paper(
        paper,
        stages=["summarize"]  # Only this stage
    )

    print(f"\n   Final state: {result.current_stage}")
    print(f"   Expected state: summarized")

    # Now we should have summary results
    if result.summary:
        print(f"\n   ✓ Summary generated:")
        print(f"     Saved to: {result.summary.saved_path}")
        print(f"     Length: {len(result.summary.summary_text):,} characters")

    # -------------------------------------------------------------------------
    # Part 3: Later, resume and complete the audio generation stage
    # -------------------------------------------------------------------------
    # The state machine remembers where we left off
    # The paper's status field is now "summarized"
    # We can resume by running just the "audio" stage

    print("\n[Part 3] Resuming to complete AUDIO GENERATION stage...")
    print("         (Paper already downloaded, extracted, and summarized)")

    # Check the paper's current state before resuming
    print(f"\n   Paper status before resume: {paper.status}")
    print(f"   State machine will validate we can transition: summarized → generating_audio")

    # Run just the audio stage
    # The state machine will:
    # 1. Verify we're in "summarized" state
    # 2. Transition: summarized → generating_audio → completed
    result = pipeline.process_paper(
        paper,
        stages=["audio"]  # Only this stage
    )

    print(f"\n   Final state: {result.current_stage}")
    print(f"   Expected state: completed")

    # Now we should have audio results
    if result.audio:
        print(f"\n   ✓ Audio generated:")
        print(f"     Saved to: {result.audio.audio_path}")
        if result.audio.audio_duration_seconds:
            print(f"     Duration: {result.audio.audio_duration_seconds:.1f} seconds")

if __name__ == "__main__":
    main()
