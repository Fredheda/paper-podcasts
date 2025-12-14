"""Service for interacting with the arXiv API."""

import time
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import arxiv

from ..models.paper import Paper, Author


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
            max_results: Maximum number of results to return
            sort_by_recent: If True, sort by most recent; otherwise by relevance

        Returns:
            List of Paper objects

        Examples:
            search_by_topic("machine learning", max_results=5)
            search_by_topic("cat:cs.AI", max_results=10)
            search_by_topic("transformers", sort_by_recent=False)
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

    def download_pdf(
        self,
        paper: Paper,
        destination: Path,
        filename: Optional[str] = None,
    ) -> Path:
        """
        Download a paper's PDF to the specified destination using arxiv library.

        Args:
            paper: The Paper object to download
            destination: Directory to save the PDF
            filename: Optional custom filename (defaults to "{arxiv_id}.pdf")

        Returns:
            Path to the downloaded PDF file
        """
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=True)

        if filename is None:
            filename = f"{paper.arxiv_id}.pdf"

        logger.info(f"Downloading PDF for {paper.arxiv_id} to {destination}")

        self._rate_limit()

        try:
            # Search for the paper to get the arxiv.Result object
            search = arxiv.Search(id_list=[paper.arxiv_id])
            result = next(self.client.results(search))

            # Download using arxiv library's download_pdf method
            output_path = result.download_pdf(dirpath=str(destination), filename=filename)

            # Update paper metadata
            paper.pdf_path = str(output_path)
            paper.downloaded_at = datetime.now()
            paper.status = "downloaded"

            logger.info(f"Successfully downloaded PDF to {output_path}")
            return Path(output_path)

        except Exception as e:
            logger.error(f"Failed to download PDF for {paper.arxiv_id}: {e}")
            raise
