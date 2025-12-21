"""Service for LLM-based paper summarization."""

import logging
from pathlib import Path
from datetime import datetime

from .llm_providers import LLMProvider
from ..models.paper import Paper
from ..models.summary_result import SummaryResult

logger = logging.getLogger(__name__)


class LLMService:
    """Service for summarizing papers using LLMs."""

    def __init__(
        self,
        provider: LLMProvider,
        prompts_dir: str = "../prompts",
    ):
        """
        Initialize the LLM service.

        Args:
            provider: LLM provider to use
            prompts_dir: Directory containing prompt templates
        """
        self.provider = provider
        self.prompts_dir = Path(prompts_dir)

        if not self.prompts_dir.exists():
            raise ValueError(f"Prompts directory does not exist: {self.prompts_dir}")

        logger.info(f"Initialized LLM service with prompts from: {self.prompts_dir}")

    def _load_prompt(self, prompt_name: str) -> str:
        """
        Load a prompt template from the prompts directory.

        Args:
            prompt_name: Name of the prompt file (without .txt extension)

        Returns:
            Prompt template string

        Raises:
            FileNotFoundError: If prompt file doesn't exist
        """
        prompt_path = self.prompts_dir / f"{prompt_name}.txt"

        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        logger.debug(f"Loading prompt from: {prompt_path}")

        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _format_prompt(
        self,
        template: str,
        paper_content: str,
        paper: Paper,
    ) -> str:
        """
        Format a prompt template with paper data.

        Args:
            template: Prompt template string
            paper_content: Extracted paper content (markdown)
            paper: Paper metadata object

        Returns:
            prompt_template: Formatted prompt string
        """
        # Format authors as comma-separated string
        authors_str = ", ".join([author.name for author in paper.authors])

        # Format published date
        published_str = paper.published.strftime("%B %Y")

        prompt_template = template.format(
            paper_content=paper_content,
            title=paper.title,
            authors=authors_str,
            published=published_str
            )

        return prompt_template

    def summarize_paper(
        self,
        paper: Paper,
        extracted_content: str,
        output_dir: str | Path,
        prompt_name: str = "summarize_paper",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> SummaryResult:
        """
        Summarize a paper using LLM and save to disk.

        Args:
            paper: Paper metadata
            extracted_content: Extracted markdown content
            output_dir: Directory where summary should be saved
            prompt_name: Prompt template name
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            SummaryResult with summary and metadata
        """

        logger.info(f"Summarizing paper: {paper.title}")

        # Load and format prompt
        prompt_template = self._load_prompt(prompt_name)
        formatted_prompt = self._format_prompt(
            prompt_template,
            extracted_content,
            paper,
        )

        # Generate summary
        summary_text = self.provider.generate(
            prompt=formatted_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Save to disk
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use cleaned title for consistent naming
        base_filename = paper.cleaned_title

        summary_filename = f"summary_{base_filename}.txt"
        summary_path = output_dir / summary_filename
        summary_path.write_text(summary_text, encoding="utf-8")

        logger.info(f"Generated and saved summary to {summary_path}")

        # Return result object
        return SummaryResult(
            summary_text=summary_text,
            saved_path=summary_path,
            summarized_at=datetime.now(),
        )
