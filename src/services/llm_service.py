"""Service for LLM-based paper summarization."""

import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

from .llm_providers import LLMProvider, AnthropicProvider
from ..models.paper import Paper
from ..models.extracted_content import ExtractedContent

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
        prompt_name: str = "summarize_paper",
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """
        Summarize a paper using the LLM.

        Args:
            paper: Paper metadata object
            extracted_content: Extracted paper content
            prompt_name: Name of the prompt template to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Summary text from the LLM
        """
        logger.info(f"Summarizing paper: {paper.title}")

        # Load and format the prompt
        prompt_template = self._load_prompt(prompt_name)
        formatted_prompt = self._format_prompt(
            prompt_template,
            extracted_content,
            paper,
        )

        # Generate summary
        summary = self.provider.generate(
            prompt=formatted_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        logger.info(f"Generated summary ({len(summary)} characters) for: {paper.title}")

        return summary

    def summarize_paper_from_files(
        self,
        paper: Paper,
        extracted_content_path: str,
        prompt_name: str = "summarize_paper",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        output_dir: Optional[str] = None,
        filename: Optional[str] = None,
    ) -> str:
        """
        Summarize a paper by loading extracted content from a file.

        Args:
            paper: Paper metadata object
            extracted_content_path: Path to the extracted content markdown file
            prompt_name: Name of the prompt template to use
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            output_dir: Optional directory to save the summary
            filename: Optional filename for the saved summary

        Returns:
            Summary text from the LLM
        """
        logger.info(f"Loading extracted content from: {extracted_content_path}")

        # Load extracted content
        with open(extracted_content_path, "r", encoding="utf-8") as f:
            markdown_content = f.read()

        summary = self.summarize_paper(
            paper=paper,
            extracted_content=markdown_content,
            prompt_name=prompt_name,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Save summary if output directory is specified
        if output_dir:
            output_path = Path(output_dir)
            output_path.mkdir(parents=True, exist_ok=True)

            filename = f"summary_{paper.pdf_filename.split(".")[0]}.txt"

            file_path = output_path / filename
            file_path.write_text(summary, encoding="utf-8")
            logger.info(f"Saved summary to: {file_path}")

        return summary
