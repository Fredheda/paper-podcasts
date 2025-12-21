"""Service for extracting content from PDF files using MarkItDown."""

import logging
from pathlib import Path
from typing import Optional
from markitdown import MarkItDown
from datetime import datetime
from ..models.extracted_content import ExtractedContent
from ..models.extraction_result import ExtractionResult


logger = logging.getLogger(__name__)


class PdfService:
    """Service for extracting markdown content from PDF files."""

    def __init__(self):
        """Initialize the PDF service with MarkItDown converter."""
        self.converter = MarkItDown()

    def extract(self, pdf_path: str | Path) -> ExtractedContent:
        """
        Extract content from a PDF as structured markdown.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            ExtractedContent with markdown

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If extraction fails

        Example:
            service = PdfService()
            content = service.extract("paper.pdf")
            print(content.markdown)
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        logger.info(f"Extracting content from {pdf_path.name}")

        try:
            # Convert PDF to markdown
            result = self.converter.convert(str(pdf_path))

            content = ExtractedContent(
                markdown=result.text_content
            )

            logger.info(
                f"Successfully extracted {len(content.markdown)} characters"
            )

            return content

        except Exception as e:
            logger.error(f"Failed to extract content from {pdf_path}: {e}")
            raise

    def save(
        self,
        content: ExtractedContent,
        output_dir: str | Path,
        base_filename: str,
    ) -> Path:
        """
        Save extracted markdown content to a file.

        Args:
            content: ExtractedContent to save
            output_dir: Directory where file should be saved
            base_filename: Base name for output file (without extension)

        Returns:
            Path to the saved markdown file

        Example:
            service = PdfService()
            content = service.extract("paper.pdf")
            saved_path = service.save(content, "output/", "my_paper")
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Always use .md extension
        output_filename = f"{base_filename}.md"
        output_path = output_dir / output_filename

        output_path.write_text(content.markdown, encoding="utf-8")

        logger.info(f"Saved markdown to {output_path}")
        return output_path

    def extract_and_save(
        self,
        pdf_path: str | Path,
        output_dir: str | Path,
        base_filename: Optional[str] = None,
    ) -> ExtractionResult:
        """
        Extract content from PDF and save it.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory where markdown should be saved
            base_filename: Base name for output file (defaults to PDF filename)

        Returns:
            ExtractionResult with content and metadata

        Example:
            service = PdfService()
            result = service.extract_and_save(
                pdf_path="paper.pdf",
                output_dir="output/extracted",
                base_filename="my_paper"
            )
            print(f"Saved to: {result.saved_path}")
        """
        # Extract content
        content = self.extract(pdf_path)

        # Determine base filename
        if base_filename is None:
            base_filename = Path(pdf_path).stem

        # Save
        saved_path = self.save(content, output_dir, base_filename)

        # Return result object
        return ExtractionResult(
            content=content,
            saved_path=saved_path,
            extracted_at=datetime.now(),
            character_count=len(content.markdown),
        )