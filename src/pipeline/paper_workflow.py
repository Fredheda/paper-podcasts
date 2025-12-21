"""State machine for paper processing workflow."""

import logging
from datetime import datetime
from typing import Optional

from statemachine import StateMachine, State

logger = logging.getLogger(__name__)


class PaperWorkflow(StateMachine):
    """
    State machine managing the paper processing lifecycle.

    States represent the processing status of a paper as it moves through
    the pipeline: download → extract → summarize → generate audio.

    The state machine ensures:
    - Valid state transitions only
    - Audit trail of state changes
    - Idempotent operations (can't download twice)
    - Clear error handling
    """

    # Define states
    new = State(initial=True, value="new")
    downloading = State(value="downloading")
    downloaded = State(value="downloaded")
    extracting = State(value="extracting")
    extracted = State(value="extracted")
    summarizing = State(value="summarizing")
    summarized = State(value="summarized")
    generating_audio = State(value="generating_audio")
    audio_generated = State(value="audio_generated")
    completed = State(final=True, value="completed")
    failed = State(final=True, value="failed")

    # Define transitions with explicit names
    start_download = new.to(downloading)
    complete_download = downloading.to(downloaded)

    start_extract = downloaded.to(extracting)
    complete_extract = extracting.to(extracted)

    start_summarize = extracted.to(summarizing)
    complete_summarize = summarizing.to(summarized)

    start_audio_generation = summarized.to(generating_audio)
    complete_audio_generation = generating_audio.to(audio_generated)

    finalize = audio_generated.to(completed)

    # Failure transitions from any non-terminal state
    mark_failed = (
        new.to(failed)
        | downloading.to(failed)
        | downloaded.to(failed)
        | extracting.to(failed)
        | extracted.to(failed)
        | summarizing.to(failed)
        | summarized.to(failed)
        | generating_audio.to(failed)
        | audio_generated.to(failed)
    )

    def __init__(self, model=None, state_field="status", start_value=None):
        """
        Initialize the workflow.

        Args:
            model: The Paper object being processed (optional)
            state_field: Field name on model to sync state to (default: "status")
            start_value: Initial state value (optional, uses model's current state if provided)
        """
        self.model = model

        # If model provided and has a status, start from that state
        if model and hasattr(model, state_field):
            start_value = getattr(model, state_field)

        super().__init__(model=model, state_field=state_field, start_value=start_value)

    # Transition hooks - executed when entering states

    def on_enter_downloading(self):
        """Called when entering downloading state."""
        logger.info(f"Starting download for paper: {self._get_paper_id()}")

    def on_enter_downloaded(self):
        """Called when download completes."""
        logger.info(f"Download completed for paper: {self._get_paper_id()}")

    def on_enter_extracting(self):
        """Called when starting PDF extraction."""
        logger.info(f"Starting extraction for paper: {self._get_paper_id()}")

    def on_enter_extracted(self):
        """Called when extraction completes."""
        logger.info(f"Extraction completed for paper: {self._get_paper_id()}")

    def on_enter_summarizing(self):
        """Called when starting summarization."""
        logger.info(f"Starting summarization for paper: {self._get_paper_id()}")

    def on_enter_summarized(self):
        """Called when summarization completes."""
        logger.info(f"Summarization completed for paper: {self._get_paper_id()}")

    def on_enter_generating_audio(self):
        """Called when starting audio generation."""
        logger.info(f"Starting audio generation for paper: {self._get_paper_id()}")

    def on_enter_audio_generated(self):
        """Called when audio generation completes."""
        logger.info(f"Audio generation completed for paper: {self._get_paper_id()}")

    def on_enter_completed(self):
        """Called when entire pipeline completes."""
        logger.info(f"Pipeline completed for paper: {self._get_paper_id()}")

    def on_enter_failed(self, error: Optional[str] = None):
        """
        Called when pipeline fails.

        Args:
            error: Optional error message
        """
        paper_id = self._get_paper_id()
        if error:
            logger.error(f"Pipeline failed for paper {paper_id}: {error}")
        else:
            logger.error(f"Pipeline failed for paper {paper_id}")

    # Helper methods

    def _get_paper_id(self) -> str:
        """Get paper identifier for logging."""
        if self.model and hasattr(self.model, "arxiv_id"):
            return self.model.arxiv_id
        return "unknown"

    def can_download(self) -> bool:
        """Check if paper can be downloaded."""
        return self.current_state == self.new

    def can_extract(self) -> bool:
        """Check if paper can be extracted."""
        return self.current_state == self.downloaded

    def can_summarize(self) -> bool:
        """Check if paper can be summarized."""
        logger.info(f"can_summarize: {self.current_state == self.extracted}")
        return self.current_state == self.extracted

    def can_generate_audio(self) -> bool:
        """Check if audio can be generated."""
        return self.current_state == self.summarized

    def can_finalize(self) -> bool:
        """Check if pipeline can be finalized."""
        return self.current_state == self.audio_generated

    def is_processing(self) -> bool:
        """Check if paper is currently being processed."""
        return self.current_state in [
            self.downloading,
            self.extracting,
            self.summarizing,
            self.generating_audio,
        ]

    def is_terminal(self) -> bool:
        """Check if in a terminal state (completed or failed)."""
        return self.current_state in [self.completed, self.failed]

    def get_next_action(self) -> Optional[str]:
        """
        Get the next action that should be performed.

        Returns:
            String describing next action, or None if terminal/processing
        """
        if self.is_processing():
            return None  # Already processing

        if self.current_state == self.new:
            return "download"
        elif self.current_state == self.downloaded:
            return "extract"
        elif self.current_state == self.extracted:
            return "summarize"
        elif self.current_state == self.summarized:
            return "generate_audio"
        elif self.current_state == self.audio_generated:
            return "finalize"
        elif self.is_terminal():
            return None

        return None
