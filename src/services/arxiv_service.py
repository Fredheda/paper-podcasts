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

    def download_paper(
        self,
        paper: Paper,
        destination_dir: str = "downloads",
    ) -> DownloadResult:
        """
        Download PDF for a paper.

        Creates the destination directory if it doesn't exist and downloads
        the PDF with a filename based on the paper's title.

        Note: Paper metadata is saved separately via the pipeline's
        paper_state.json file, not here.

        Creates:
        - {cleaned_title}.pdf

        Args:
            paper: Paper object to download
            destination_dir: Directory where PDF should be saved

        Returns:
            DownloadResult with paths and metadata about the download

        Raises:
            Exception: If PDF download fails
        """
        destination_path = Path(destination_dir)
        destination_path.mkdir(parents=True, exist_ok=True)

        # Create filename from cleaned paper title
        pdf_filename = f"{paper.cleaned_title}.pdf"

        logger.info(f"Downloading PDF for {paper.arxiv_id} to {destination_path}")

        self._rate_limit()

        try:
            # Search for the paper to get the arxiv.Result object
            search = arxiv.Search(id_list=[paper.arxiv_id])
            result = next(self.client.results(search))

            # Download using arxiv library's download_pdf method
            output_path = result.download_pdf(
                dirpath=str(destination_path),
                filename=pdf_filename
            )

            pdf_path = Path(output_path)
            downloaded_at = datetime.now()

            logger.info(f"Successfully downloaded PDF to {pdf_path}")

            return DownloadResult(
                pdf_path=pdf_path,
                save_dir=destination_path,
                pdf_filename=pdf_filename,
                downloaded_at=downloaded_at,
            )

        except Exception as e:
            logger.error(f"Failed to download PDF for {paper.arxiv_id}: {e}")
            raise
