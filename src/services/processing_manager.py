"""Background processing manager for paper pipeline jobs."""

from __future__ import annotations

import copy
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, List, Optional

from src.models.paper import Paper


@dataclass
class ProcessingJob:
    """Current processing metadata for one paper."""

    arxiv_id: str
    title: str
    stage: str
    message: str
    progress: float
    is_active: bool = False
    queue_position: Optional[int] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ProcessingManager:
    """Runs pipeline work on a dedicated worker thread and tracks status."""

    _PROGRESS_MAP = {
        "queued": 0.0,
        "downloading": 0.10,
        "extracting": 0.40,
        "summarizing": 0.65,
        "generating_audio": 0.85,
        "completed": 1.0,
        "failed": 1.0,
    }

    _ORDER_MAP = {
        "downloading": 0,
        "extracting": 1,
        "summarizing": 2,
        "generating_audio": 3,
        "queued": 4,
        "failed": 5,
        "completed": 6,
    }

    def __init__(self, pipeline, max_concurrent: int = 5):
        self._pipeline = pipeline
        self._max_concurrent = max(1, max_concurrent)
        self._jobs: Dict[str, ProcessingJob] = {}
        self._papers: Dict[str, Paper] = {}
        self._queue: Deque[str] = deque()
        self._active_paper_ids: set[str] = set()
        self._shutdown = False

        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._workers: List[threading.Thread] = []
        for _ in range(self._max_concurrent):
            worker = threading.Thread(target=self._worker_loop, daemon=True)
            self._workers.append(worker)
            worker.start()

    def enqueue(self, paper: Paper) -> bool:
        """Queue a paper for processing. Returns False if already queued/active."""
        arxiv_id = paper.arxiv_id
        title = paper.title
        now = datetime.now()

        with self._condition:
            if self._is_queued_or_active_locked(arxiv_id):
                return False

            self._papers[arxiv_id] = copy.deepcopy(paper)
            self._jobs[arxiv_id] = ProcessingJob(
                arxiv_id=arxiv_id,
                title=title,
                stage="queued",
                message="Queued for processing",
                progress=self._PROGRESS_MAP["queued"],
                is_active=False,
                queue_position=len(self._queue) + 1,
                started_at=None,
                updated_at=now,
            )
            self._queue.append(arxiv_id)
            self._recompute_queue_positions_locked()
            self._condition.notify()

        return True

    def has_active_jobs(self) -> bool:
        """Return whether there is active or queued work."""
        with self._lock:
            return bool(self._active_paper_ids) or len(self._queue) > 0

    def get_jobs(self) -> List[ProcessingJob]:
        """Return a sorted snapshot of all known jobs."""
        with self._lock:
            snapshot = [copy.deepcopy(job) for job in self._jobs.values()]

        return sorted(
            snapshot,
            key=lambda job: (
                0 if job.is_active else 1,
                self._ORDER_MAP.get(job.stage, 99),
                job.queue_position or 999,
                job.updated_at or datetime.min,
            ),
        )

    def get_counts(self) -> Dict[str, int]:
        """Return basic counters for queue/active/completed/failed."""
        with self._lock:
            queued = len(self._queue)
            active = len(self._active_paper_ids)
            completed = len([j for j in self._jobs.values() if j.stage == "completed"])
            failed = len([j for j in self._jobs.values() if j.stage == "failed"])

        return {
            "queued": queued,
            "active": active,
            "completed": completed,
            "failed": failed,
        }

    def shutdown(self) -> None:
        """Stop the worker thread gracefully."""
        with self._condition:
            self._shutdown = True
            self._condition.notify_all()

        for worker in self._workers:
            if worker.is_alive():
                worker.join(timeout=2.0)

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                while not self._queue and not self._shutdown:
                    self._condition.wait(timeout=1.0)

                if self._shutdown:
                    return

                paper_id = self._queue.popleft()
                self._active_paper_ids.add(paper_id)
                self._recompute_queue_positions_locked()
                self._set_stage_locked(
                    paper_id,
                    stage="downloading",
                    message="Downloading PDF",
                    is_active=True,
                )

            try:
                paper = self._papers[paper_id]
                self._run_stage(paper_id, paper, "download", "downloading", "Downloading PDF")
                self._run_stage(paper_id, paper, "extract", "extracting", "Extracting text")
                self._run_stage(paper_id, paper, "summarize", "summarizing", "Generating summary")
                self._run_stage(
                    paper_id,
                    paper,
                    "audio",
                    "generating_audio",
                    "Generating audio",
                )
                self._set_stage(
                    paper_id,
                    stage="completed",
                    message="Processing complete",
                    is_active=False,
                    queue_position=None,
                    error=None,
                )
            except Exception as exc:
                self._set_stage(
                    paper_id,
                    stage="failed",
                    message="Processing failed",
                    is_active=False,
                    queue_position=None,
                    error=str(exc),
                )
            finally:
                with self._lock:
                    self._active_paper_ids.discard(paper_id)
                    self._recompute_queue_positions_locked()

    def _run_stage(
        self,
        paper_id: str,
        paper: Paper,
        pipeline_stage: str,
        ui_stage: str,
        message: str,
    ) -> None:
        self._set_stage(
            paper_id,
            stage=ui_stage,
            message=message,
            is_active=True,
            queue_position=None,
            error=None,
        )
        result = self._pipeline.process_paper(paper, stages=[pipeline_stage])
        if result.errors:
            raise RuntimeError(result.errors[0])

    def _is_queued_or_active_locked(self, paper_id: str) -> bool:
        if paper_id in self._active_paper_ids:
            return True
        return paper_id in self._queue

    def _recompute_queue_positions_locked(self) -> None:
        for index, queued_id in enumerate(self._queue, start=1):
            job = self._jobs.get(queued_id)
            if job:
                job.queue_position = index
                job.is_active = False
                job.updated_at = datetime.now()

    def _set_stage(
        self,
        paper_id: str,
        stage: str,
        message: str,
        is_active: bool,
        queue_position: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._set_stage_locked(
                paper_id=paper_id,
                stage=stage,
                message=message,
                is_active=is_active,
                queue_position=queue_position,
                error=error,
            )

    def _set_stage_locked(
        self,
        paper_id: str,
        stage: str,
        message: str,
        is_active: bool,
        queue_position: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        now = datetime.now()
        job = self._jobs[paper_id]

        job.stage = stage
        job.message = message
        job.progress = self._PROGRESS_MAP.get(stage, 0.0)
        job.is_active = is_active
        job.error = error
        job.queue_position = queue_position
        if job.started_at is None:
            job.started_at = now
        job.updated_at = now
        if stage in {"completed", "failed"}:
            job.completed_at = now
