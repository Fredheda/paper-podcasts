"""Service for interacting with the arXiv API."""

import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List
import arxiv
from ..models.paper import Paper, Author
from ..models.download_result import DownloadResult


logger = logging.getLogger(__name__)


class ArxivService:
    """Service for searching and downloading papers from arXiv."""

    def __init__(self, rate_limit_delay: float = 3.0):
        """
        Initialize the arXiv service.

        Args:
            rate_limit_delay: Delay in seconds between API requests (arXiv recommends 3 seconds)
        """
        self.rate_limit_delay = rate_limit_delay
        self.last_request_time = 0.0
        self.client = arxiv.Client()

    def _rate_limit(self):
        """Enforce rate limiting between API requests."""
        current_time = time.time()
        time_since_last_request = current_time - self.last_request_time

        if time_since_last_request < self.rate_limit_delay:
            sleep_time = self.rate_limit_delay - time_since_last_request
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)

        self.last_request_time = time.time()

    @staticmethod
    def _clean_filename(title: str, max_length: int = 200) -> str:
        """
        Clean a paper title for use as a filename.

        Removes invalid filename characters and normalizes whitespace.

        Args:
            title: The paper title to clean
            max_length: Maximum length for the filename (default: 200)

        Returns:
            Cleaned filename string

        """
        # Remove invalid filename characters: / \ : * ? " < > |
        invalid_chars = '/\\:*?"<>|'
        cleaned = title
        for char in invalid_chars:
            cleaned = cleaned.replace(char, '_')

        # Replace multiple spaces with single space, then spaces with underscores
        cleaned = ' '.join(cleaned.split())
        cleaned = cleaned.replace(' ', '_')

        # Limit length to avoid filesystem issues
        cleaned = cleaned[:max_length]

        return cleaned

    def _arxiv_result_to_paper(self, result: arxiv.Result) -> Paper:
        """
        Convert an arxiv.Result object to our Paper model.

        Args:
            result: The arxiv.Result object from the API

        Returns:
            Paper object with all metadata
        """
        authors = [Author(name=author.name) for author in result.authors]

        return Paper(
            arxiv_id=result.entry_id.split("/")[-1],  # Extract ID from URL
            title=result.title,
            authors=authors,
            abstract=result.summary,
            published=result.published,
            updated=result.updated,
            categories=result.categories,
            primary_category=result.primary_category,
            pdf_url=result.pdf_url,
            comment=result.comment,
            journal_ref=result.journal_ref,
            doi=result.doi,
        )

    def search_by_topic(
        self,
        topic: str,
        exact: bool = True,
        max_results: int = 10,
    ) -> List[Paper]:
        """
        Search for papers on a specific topic.

        Args:
            topic: The search topic (keywords, categories, etc.)
                   Examples: "machine learning", "cat:cs.AI", "quantum computing"
            exact: If True, search for exact phrase and sort by relevance;
                   If False, search broadly and sort by submission date
            max_results: Maximum number of results to return

        Returns:
            List of Paper objects
        """
        logger.info(f"Searching for papers on topic: '{topic}'")

        if exact:
            topic = f'"{topic}"'
            sort_criterion = arxiv.SortCriterion.Relevance
        else:
            sort_criterion = arxiv.SortCriterion.SubmittedDate

        search = arxiv.Search(
            query=topic,
            max_results=max_results,
            sort_by=sort_criterion,
            sort_order=arxiv.SortOrder.Descending,
        )

        self._rate_limit()
        papers = []
        
        try:
            for result in self.client.results(search):
                paper = self._arxiv_result_to_paper(result)
                papers.append(paper)
                logger.debug(f"Found paper: {paper.title[:50]}... ({paper.arxiv_id})")

        except Exception as e:
            logger.error(f"Error searching arXiv: {e}")
            raise

        logger.info(f"Found {len(papers)} papers")
        return papers

    def _download_pdf(
        self,
        arxiv_id: str,
        destination_dir: str,
        filename: str,
    ) -> Path:
        """
        Internal method to download a PDF from arXiv.

        Args:
            arxiv_id: The arXiv ID of the paper
            destination_dir: Directory to save the PDF
            filename: Filename for the PDF

        Returns:
            Path to the downloaded PDF file
        """

        logger.info(f"Downloading PDF for {arxiv_id} to {destination_dir}")

        self._rate_limit()

        try:
            # Search for the paper to get the arxiv.Result object
            search = arxiv.Search(id_list=[arxiv_id])
            result = next(self.client.results(search))

            # Download using arxiv library's download_pdf method
            output_path = result.download_pdf(dirpath=str(destination_dir), filename=filename)

            logger.info(f"Successfully downloaded PDF to {output_path}")
            return Path(output_path)

        except Exception as e:
            logger.error(f"Failed to download PDF for {arxiv_id}: {e}")
            raise

    def _save_metadata(
        self,
        paper: Paper,
        destination_dir: str,
        filename: str,
    ) -> Path:
        """
        Internal method to save paper metadata to JSON.

        Args:
            paper: Paper object to save
            destination_dir: Directory where metadata should be saved
            filename: Filename for the metadata JSON

        Returns:
            Path to the saved metadata file
        """
        logger.info(f"Saving metadata for {paper.arxiv_id} to {destination_dir}")

        try:
            metadata_path = Path(destination_dir) / filename

            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(paper.to_dict(), f, indent=4)

            logger.info(f"Successfully saved metadata to {metadata_path}")
            return metadata_path

        except Exception as e:
            logger.error(f"Failed to save metadata for {paper.arxiv_id}: {e}")
            raise

    def download_and_save_metadata(
        self,
        paper: Paper,
        destination_dir: str = "downloads",
    ) -> DownloadResult:
        """
        Download PDF and save metadata with matching filenames.

        This is a convenience method that ensures the PDF and metadata
        files have matching names in the same directory.

        Creates:
        - {cleaned_title}.pdf
        - {cleaned_title}.json

        Args:
            paper: Paper object to download and save (not modified)
            destination_dir: Directory for both PDF and metadata

        Returns:
            DownloadResult with paths and metadata about the download
        """
        destination_path = Path(destination_dir)
        destination_path.mkdir(parents=True, exist_ok=True)

        # Clean title for use as filename
        base_filename = self._clean_filename(paper.title)

        pdf_filename = f"{base_filename}.pdf"
        metadata_filename = f"{base_filename}.json"

        # Download PDF with specific filename
        pdf_path = self._download_pdf(
            paper.arxiv_id,
            str(destination_path),
            pdf_filename
        )

        # Record download time after successful download
        downloaded_at = datetime.now()

        # Save metadata using existing method
        # (This only saves arXiv metadata, not download info)
        metadata_path = self._save_metadata(
            paper,
            str(destination_path),
            metadata_filename
        )

        logger.info(
            f"Downloaded and saved metadata for {paper.title} to {destination_path}"
        )

        # Return DownloadResult with all download info
        # (This is where download-specific info lives, not in Paper)
        return DownloadResult(
            pdf_path=pdf_path,
            metadata_path=metadata_path,
            save_dir=destination_path,
            pdf_filename=pdf_filename,
            metadata_filename=metadata_filename,
            downloaded_at=downloaded_at,
        )
