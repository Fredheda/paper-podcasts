"""Service for extracting content from PDF files using MarkItDown."""

import logging
from pathlib import Path
from typing import Optional
from markitdown import MarkItDown
from ..models.extracted_content import ExtractedContent


logger = logging.getLogger(__name__)


class PdfService:
    """Service for extracting markdown content from PDF files."""

    def __init__(self):
        """Initialize the PDF service with MarkItDown converter."""
        self.converter = MarkItDown()

    def extract(self, paper: str) -> ExtractedContent:
        """
        Extract content from a PDF as structured markdown.

        Args:
            pdf_path: Path to the PDF file

        Returns:
            ExtractedContent with markdown and metadata

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            Exception: If extraction fails

        Example:
            service = PdfService()
            content = service.extract("paper.pdf")
            print(content.markdown)
        """

        if not Path(paper.pdf_path).exists():
            raise FileNotFoundError(f"PDF file not found: {paper.pdf_path}")

        logger.info(f"Extracting content from {paper.title}")

        try:
            # Convert PDF to markdown
            result = self.converter.convert(paper.pdf_path)

            content = ExtractedContent(
                markdown=result.text_content
            )

            logger.info(
                f"Successfully extracted content from {paper.title} "
                f"({len(content.markdown)} chars)"
            )

            return content

        except Exception as e:
            logger.error(f"Failed to extract content from {paper.title}: {e}")
            raise

    def save(
        self,
        content: ExtractedContent,
        filename: str,
        output_dir: str = "extracted_content",
    ) -> Path:
        """
        Save extracted markdown content to a text file.

        Args:
            content: ExtractedContent object to save
            output_dir: Directory where file should be saved
            filename: Output filename (defaults to title-based name)

        Returns:
            Path to the saved file

        Example:
            service = PdfService()
            content = service.extract("paper.pdf")
            service.save(content, "output/", "paper.txt")
        """
        output_dir = Path(output_dir)
        filename = Path(f"{filename.split(".")[0]}.md")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / filename
        output_path.write_text(content.markdown, encoding="utf-8")

        logger.info(f"Saved markdown to {output_path}")
        return output_path

    def extract_and_save(
        self,
        pdf_path: str,
        filename: str,
        output_dir: str = "extracted_content",
        
    ) -> tuple[Path, ExtractedContent]:
        """
        Extract content from PDF and save it in one step.

        Args:
            pdf_path: Path to the PDF file
            output_dir: Directory where file should be saved
            filename: Output filename (optional)

        Returns:
            Tuple of (saved_file_path, extracted_content)

        Example:
            service = PdfService()
            file_path, content = service.extract_and_save(
                "paper.pdf",
                "output/"
            )
        """
        content = self.extract(pdf_path)
        output_path = self.save(content, filename, output_dir)

        return output_path, content