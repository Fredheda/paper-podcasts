"""Orchestrator for the paper processing pipeline."""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .paper_workflow import PaperWorkflow
from ..models.paper import Paper
from ..models.download_result import DownloadResult
from ..models.extraction_result import ExtractionResult
from ..models.extracted_content import ExtractedContent
from ..models.summary_result import SummaryResult
from ..models.audio_result import AudioResult
from ..services.arxiv_service import ArxivService
from ..services.pdf_service import PdfService
from ..services.llm_service import LLMService
from ..services.audio_service import AudioService

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete result of processing a paper through the pipeline."""

    paper: Paper
    workflow: PaperWorkflow
    download: Optional[DownloadResult] = None
    extraction: Optional[ExtractionResult] = None
    summary: Optional[SummaryResult] = None
    audio: Optional[AudioResult] = None
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    @property
    def is_successful(self) -> bool:
        """Check if pipeline completed successfully."""
        return self.workflow.current_state == self.workflow.completed

    @property
    def is_failed(self) -> bool:
        """Check if pipeline failed."""
        return self.workflow.current_state == self.workflow.failed

    @property
    def current_stage(self) -> str:
        """Get current pipeline stage."""
        return self.workflow.current_state.id

    def to_dict(self) -> dict:
        """Convert pipeline result to dictionary."""
        return {
            "paper_id": self.paper.arxiv_id,
            "paper_title": self.paper.title,
            "current_state": self.current_stage,
            "is_successful": self.is_successful,
            "is_failed": self.is_failed,
            "download": {
                "pdf_path": str(self.download.pdf_path) if self.download else None,
                "metadata_path": str(self.download.metadata_path)
                if self.download
                else None,
            }
            if self.download
            else None,
            "extraction": {
                "saved_path": str(self.extraction.saved_path)
                if self.extraction
                else None,
                "character_count": self.extraction.character_count
                if self.extraction
                else 0,
            }
            if self.extraction
            else None,
            "summary": self.summary.to_dict() if self.summary else None,
            "audio": self.audio.to_dict() if self.audio else None,
            "errors": self.errors,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class PaperPipeline:
    """
    Orchestrates the full paper-to-podcast pipeline.

    The pipeline processes papers through multiple stages:
    1. Download: Fetch PDF and metadata from arXiv
    2. Extract: Convert PDF to markdown
    3. Summarize: Generate summary using LLM
    4. Audio: Generate podcast audio (future)

    The pipeline uses a state machine to track progress and ensure
    valid transitions. It handles errors gracefully and preserves
    partial results.
    """

    def __init__(
        self,
        arxiv_service: ArxivService,
        pdf_service: PdfService,
        llm_service: LLMService,
        audio_service: AudioService,
        storage_dir: Path,
    ):
        """
        Initialize the pipeline with required services.

        Args:
            arxiv_service: Service for downloading papers from arXiv
            pdf_service: Service for extracting content from PDFs
            llm_service: Service for generating summaries
            audio_service: Service for generating audio
            storage_dir: Root directory for storing artifacts
        """
        self.arxiv = arxiv_service
        self.pdf = pdf_service
        self.llm = llm_service
        self.audio = audio_service
        self.storage_dir = Path(storage_dir)

        # Create storage directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Initialized pipeline with storage at: {self.storage_dir}")

    def process_paper(
        self,
        paper: Paper,
        stages: Optional[List[str]] = None,
    ) -> PipelineResult:
        """
        Process a paper through the pipeline.

        Args:
            paper: Paper object to process
            stages: List of stages to run (default: all stages)
                   Options: ["download", "extract", "summarize", "audio"]

        Returns:
            PipelineResult with complete results and any errors
        """
        # Initialize workflow from paper's current state
        workflow = PaperWorkflow(model=paper)

        # Create result object
        result = PipelineResult(paper=paper, workflow=workflow)

        # Default to all stages including audio
        stages = stages or ["download", "extract", "summarize", "audio"]

        logger.info(
            f"Starting pipeline for {paper.arxiv_id} from state: {workflow.current_state.id}"
        )

        try:
            # Download stage
            if "download" in stages and workflow.can_download():
                result.download = self._stage_download(paper, workflow)

            # Extract stage - lazy load download result if needed
            if "extract" in stages and workflow.can_extract():
                if not result.download:
                    result.download = self._load_download_result(paper)
                if result.download:
                    result.extraction = self._stage_extract(paper, result.download, workflow)

            # Summarize stage - lazy load extraction result if needed
            if "summarize" in stages and workflow.can_summarize():
                if not result.extraction:
                    result.extraction = self._load_extraction_result(paper)
                if result.extraction:
                    result.summary = self._stage_summarize(
                        paper, result.extraction, workflow
                    )

            # Audio stage - lazy load summary result if needed
            if "audio" in stages and workflow.can_generate_audio():
                if not result.summary:
                    result.summary = self._load_summary_result(paper)
                if result.summary:
                    result.audio = self._stage_audio(paper, result.summary, workflow)

            # Finalize pipeline if audio generation is complete
            if workflow.can_finalize():
                workflow.finalize()
                self._save_paper_state(paper)

        except Exception as e:
            error_msg = f"Pipeline error: {str(e)}"
            result.errors.append(error_msg)
            workflow.mark_failed(error=error_msg)
            self._save_paper_state(paper)
            logger.error(f"Pipeline failed for {paper.arxiv_id}: {e}", exc_info=True)

        finally:
            result.completed_at = datetime.now()

        logger.info(
            f"Pipeline finished for {paper.arxiv_id}. "
            f"Final state: {workflow.current_state.id}"
        )

        return result

    def _stage_download(
        self, paper: Paper, workflow: PaperWorkflow
    ) -> DownloadResult:
        """
        Execute download stage.

        Args:
            paper: Paper to download
            workflow: State machine to update

        Returns:
            DownloadResult with paths and metadata
        """
        logger.info(f"[DOWNLOAD] Starting for {paper.arxiv_id}")
        workflow.start_download()

        try:
            # Create paper-specific directory
            download_dir = self.storage_dir / "papers" / paper.arxiv_id

            # Download paper
            result = self.arxiv.download_and_save_metadata(paper, str(download_dir))

            workflow.complete_download()
            self._save_paper_state(paper)
            logger.info(f"[DOWNLOAD] Completed for {paper.arxiv_id}")

            return result

        except Exception as e:
            logger.error(f"[DOWNLOAD] Failed for {paper.arxiv_id}: {e}")
            raise

    def _stage_extract(
        self, paper: Paper, download: DownloadResult, workflow: PaperWorkflow
    ) -> ExtractionResult:
        """
        Execute extraction stage.

        Args:
            paper: Paper being processed
            download: Result from download stage
            workflow: State machine to update

        Returns:
            ExtractionResult with extracted content
        """
        logger.info(f"[EXTRACT] Starting for {download.pdf_path}")
        workflow.start_extract()

        try:
            # Extract and save content from PDF (returns ExtractionResult)
            extract_dir = download.save_dir / "extracted"
            base_filename = Path(download.pdf_filename).stem

            result = self.pdf.extract_and_save(
                pdf_path=download.pdf_path,
                output_dir=extract_dir,
                base_filename=base_filename,
            )

            workflow.complete_extract()
            self._save_paper_state(paper)
            logger.info(
                f"[EXTRACT] Completed. Saved to {result.saved_path} "
                f"({result.character_count} chars)"
            )

            return result

        except Exception as e:
            logger.error(f"[EXTRACT] Failed: {e}")
            raise

    def _stage_summarize(
        self, paper: Paper, extraction: ExtractionResult, workflow: PaperWorkflow
    ) -> SummaryResult:
        """
        Execute summarization stage.

        Args:
            paper: Paper being summarized
            extraction: Result from extraction stage
            workflow: State machine to update

        Returns:
            SummaryResult with summary text and metadata
        """
        logger.info(f"[SUMMARIZE] Starting for {paper.arxiv_id}")
        workflow.start_summarize()

        try:
            # Summary directory
            summary_dir = extraction.saved_path.parent.parent / "summaries"

            # Generate summary using service (returns SummaryResult directly)
            result = self.llm.summarize_paper(
                paper=paper,
                extracted_content=extraction.content.markdown,
                output_dir=summary_dir,
                prompt_name="summarize_paper",
            )

            workflow.complete_summarize()
            self._save_paper_state(paper)
            logger.info(f"[SUMMARIZE] Completed. Saved to {result.saved_path}")

            return result

        except Exception as e:
            logger.error(f"[SUMMARIZE] Failed: {e}")
            raise

    def _stage_audio(
        self, paper: Paper, summary: SummaryResult, workflow: PaperWorkflow
    ) -> AudioResult:
        """
        Execute audio generation stage.

        Args:
            paper: Paper being processed
            summary: Result from summarization stage
            workflow: State machine to update

        Returns:
            AudioResult with audio file and metadata
        """
        logger.info(f"[AUDIO] Starting audio generation")
        workflow.start_audio_generation()

        try:
            # Audio directory
            audio_dir = summary.saved_path.parent.parent / "audio"

            # Determine base filename
            base_filename = summary.saved_path.stem.replace("summary_", "")

            # Generate audio
            result = self.audio.generate_audio(
                text=summary.summary_text,
                output_dir=audio_dir,
                base_filename=base_filename,
            )

            workflow.complete_audio_generation()
            self._save_paper_state(paper)
            logger.info(f"[AUDIO] Completed. Saved to {result.audio_path}")

            return result

        except Exception as e:
            logger.error(f"[AUDIO] Failed: {e}")
            raise

    def resume_paper(self, paper: Paper) -> PipelineResult:
        """
        Resume processing a paper from its current state.

        This is useful for retrying failed papers or continuing
        partially processed papers.

        Args:
            paper: Paper to resume (with current status set)

        Returns:
            PipelineResult
        """
        logger.info(f"Resuming paper {paper.arxiv_id} from state: {paper.status}")

        # Determine which stages to run based on current state
        workflow = PaperWorkflow(model=paper)

        if workflow.current_state == workflow.new:
            stages = ["download", "extract", "summarize", "audio"]
        elif workflow.current_state == workflow.downloaded:
            stages = ["extract", "summarize", "audio"]
        elif workflow.current_state == workflow.extracted:
            stages = ["summarize", "audio"]
        elif workflow.current_state == workflow.summarized:
            stages = ["audio"]
        elif workflow.current_state == workflow.audio_generated:
            # Just need to finalize
            stages = []
            workflow.finalize()
        elif workflow.current_state == workflow.failed:
            logger.warning(
                f"Cannot resume from failed state. "
                "Failed is a terminal state - create a new paper instance to retry."
            )
            stages = []
        else:
            logger.warning(
                f"Cannot resume from state {workflow.current_state.id}. "
                "Paper may already be complete or in processing state."
            )
            stages = []

        return self.process_paper(paper, stages=stages)

    def _load_download_result(self, paper: Paper) -> Optional[DownloadResult]:
        """
        Reconstruct DownloadResult from disk if files exist.

        Args:
            paper: Paper to load download result for

        Returns:
            DownloadResult if files exist, None otherwise
        """
        download_dir = self.storage_dir / "papers" / paper.arxiv_id

        if not download_dir.exists():
            return None

        # Find PDF and JSON files in the paper's directory
        pdf_files = list(download_dir.glob("*.pdf"))
        json_files = list(download_dir.glob("*.json"))

        if pdf_files and json_files:
            pdf_path = pdf_files[0]
            metadata_path = json_files[0]

            logger.info(f"Loading existing download result for {paper.arxiv_id}")
            return DownloadResult(
                pdf_path=pdf_path,
                metadata_path=metadata_path,
                save_dir=download_dir,
                pdf_filename=pdf_path.name,
                metadata_filename=metadata_path.name,
                downloaded_at=datetime.fromtimestamp(pdf_path.stat().st_mtime),
            )

        return None

    def _load_extraction_result(self, paper: Paper) -> Optional[ExtractionResult]:
        """
        Reconstruct ExtractionResult from disk if files exist.

        Args:
            paper: Paper to load extraction result for

        Returns:
            ExtractionResult if files exist, None otherwise
        """
        download_dir = self.storage_dir / "papers" / paper.arxiv_id
        extract_dir = download_dir / "extracted"

        if not extract_dir.exists():
            return None

        # Find markdown files in the extracted directory
        md_files = list(extract_dir.glob("*.md"))

        if md_files:
            markdown_path = md_files[0]
            logger.info(f"Loading existing extraction result for {paper.arxiv_id}")
            # Read the markdown content from disk
            markdown_content = markdown_path.read_text(encoding="utf-8")

            return ExtractionResult(
                content=ExtractedContent(markdown=markdown_content),
                saved_path=markdown_path,
                extracted_at=datetime.fromtimestamp(markdown_path.stat().st_mtime),
                character_count=len(markdown_content),
            )

        return None

    def _load_summary_result(self, paper: Paper) -> Optional[SummaryResult]:
        """
        Reconstruct SummaryResult from disk if files exist.

        Args:
            paper: Paper to load summary result for

        Returns:
            SummaryResult if files exist, None otherwise
        """
        download_dir = self.storage_dir / "papers" / paper.arxiv_id
        summary_dir = download_dir / "summaries"

        if not summary_dir.exists():
            return None

        # Find summary text files
        summary_files = list(summary_dir.glob("summary_*.txt"))

        if summary_files:
            summary_path = summary_files[0]
            logger.info(f"Loading existing summary result for {paper.arxiv_id}")
            # Read the summary content from disk
            summary_content = summary_path.read_text(encoding="utf-8")

            return SummaryResult(
                summary_text=summary_content,
                saved_path=summary_path,
                summarized_at=datetime.fromtimestamp(summary_path.stat().st_mtime),
            )

        return None

    def _load_audio_result(self, paper: Paper) -> Optional[AudioResult]:
        """
        Reconstruct AudioResult from disk if files exist.

        Args:
            paper: Paper to load audio result for

        Returns:
            AudioResult if files exist, None otherwise
        """
        download_dir = self.storage_dir / "papers" / paper.arxiv_id
        audio_dir = download_dir / "audio"

        if not audio_dir.exists():
            return None

        # Find audio files (mp3)
        audio_files = list(audio_dir.glob("*.mp3"))

        if audio_files:
            audio_path = audio_files[0]
            logger.info(f"Loading existing audio result for {paper.arxiv_id}")

            return AudioResult(
                audio_path=audio_path,
                generated_at=datetime.fromtimestamp(audio_path.stat().st_mtime),
            )

        return None

    def _save_paper_state(self, paper: Paper) -> None:
        """
        Save paper state to disk for persistence across runs.

        Args:
            paper: Paper to save
        """
        try:
            state_file = paper.save_to_disk(self.storage_dir)
            logger.debug(f"Saved paper state to {state_file}")
        except Exception as e:
            logger.warning(f"Failed to save paper state: {e}")

    def load_paper(self, arxiv_id: str) -> Optional[Paper]:
        """
        Load a paper's state from disk.

        This allows resuming processing across different script runs.

        Args:
            arxiv_id: ArXiv ID of the paper to load

        Returns:
            Paper object if found, None otherwise

        Example:
            # In script run 1
            result = pipeline.process_paper(paper, stages=["download", "extract"])

            # In script run 2 (days later)
            paper = pipeline.load_paper("2301.12345")
            if paper:
                result = pipeline.process_paper(paper, stages=["summarize"])
        """
        return Paper.load_from_disk(arxiv_id, self.storage_dir)
