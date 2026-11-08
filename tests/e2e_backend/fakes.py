"""Scripted stand-ins for the three network-bound services.

Each fake keeps the real method's signature (a test pins it) and is chosen by
keywords in its input, so a browser test needs no per-test wiring.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional

from src.models.download_result import DownloadResult
from src.models.paper import Author, Paper
from src.services.arxiv_service import ArxivService
from src.services.llm_providers import ChatTurn, OpenAIProvider
from src.services.tts_providers import OpenAITTSProvider

from .media import make_mp3, make_pdf

SUMMARY_HTML = (
    "<h2>Scripted summary</h2>"
    "<p>This paper is a fixture.</p>"
    "<ul><li>Point one</li><li>Point two</li></ul>"
    "<script>window.__summary_script_ran = true</script>"
)
CHAT_CHUNKS = ("First chunk. ", "Second chunk. ", "Third chunk.")
GATE_TIMEOUT_SECONDS = 30.0


class Recorder:
    """Request log and the gate that holds a `slow` chat stream."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: list[dict[str, Any]] = []
        self.gate = threading.Event()

    def record(self, kind: str, **data: Any) -> None:
        with self._lock:
            self._requests.append({"kind": kind, **data})

    def requests(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._requests)

    def reset(self) -> None:
        with self._lock:
            self._requests.clear()
        self.gate.clear()


def scripted_papers() -> List[Paper]:
    """Three fixed search results; the third one makes the summary step fail."""
    titles = {
        "2501.00001": "Scripted Paper One",
        "2501.00002": "Scripted Paper Two",
        "2501.00003": "FAIL Scripted Paper Three",
    }
    when = datetime(2025, 1, 1)
    return [
        Paper(
            arxiv_id=arxiv_id,
            title=title,
            authors=[Author(name="Ada Lovelace")],
            abstract=f"Abstract of {title}.",
            published=when,
            updated=when,
            categories=["cs.AI"],
            primary_category="cs.AI",
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}",
        )
        for arxiv_id, title in titles.items()
    ]


def _search_by_topic(recorder: Recorder) -> Callable[..., List[Paper]]:
    def search_by_topic(
        self: ArxivService,
        topic: str,
        exact: bool = True,
        max_results: int = 10,
    ) -> List[Paper]:
        recorder.record("search", topic=topic, exact=exact, max_results=max_results)
        return [] if topic.strip() == "none" else scripted_papers()

    return search_by_topic


def _download_paper(recorder: Recorder) -> Callable[..., DownloadResult]:
    def download_paper(
        self: ArxivService,
        paper: Paper,
        destination_dir: str = "downloads",
    ) -> DownloadResult:
        recorder.record("download", arxiv_id=paper.arxiv_id)
        destination = Path(destination_dir)
        destination.mkdir(parents=True, exist_ok=True)
        filename = f"{paper.cleaned_title}.pdf"
        pdf = make_pdf(
            [paper.title, "Abstract", paper.abstract, "Body text of the fixture."]
        )
        (destination / filename).write_bytes(pdf)
        return DownloadResult(
            pdf_path=destination / filename,
            save_dir=destination,
            pdf_filename=filename,
            downloaded_at=datetime.now(),
        )

    return download_paper


def _generate(recorder: Recorder) -> Callable[..., str]:
    def generate(
        self: OpenAIProvider,
        prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        recorder.record("summary", prompt=prompt)
        if "FAIL" in prompt:
            raise RuntimeError("scripted LLM failure")
        return SUMMARY_HTML

    return generate


def _stream_chat(recorder: Recorder) -> Callable[..., Iterator[str]]:
    def stream_chat(
        self: OpenAIProvider,
        messages: List[ChatTurn],
        system: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> Iterator[str]:
        recorder.record("chat", system=system, messages=[dict(m) for m in messages])
        question = messages[-1]["content"] if messages else ""
        yield CHAT_CHUNKS[0]
        if "slow" in question:
            recorder.gate.wait(timeout=GATE_TIMEOUT_SECONDS)
        if "boom" in question:
            raise RuntimeError("scripted stream failure")
        yield CHAT_CHUNKS[1]
        yield CHAT_CHUNKS[2]

    return stream_chat


def _generate_audio(recorder: Recorder) -> Callable[..., str]:
    def generate_audio(
        self: OpenAITTSProvider,
        text: str,
        voice: Optional[str] = None,
        output_path: Optional[str | Path] = None,
    ) -> str:
        recorder.record("tts", text=text)
        if output_path is None:
            raise ValueError("output_path is required")
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(make_mp3())
        return str(target)

    return generate_audio


def install_fakes(recorder: Recorder) -> Callable[[], None]:
    """Patch the five methods in place; return a function that undoes it."""
    targets: list[tuple[type, str, Callable[..., Any]]] = [
        (ArxivService, "search_by_topic", _search_by_topic(recorder)),
        (ArxivService, "download_paper", _download_paper(recorder)),
        (OpenAIProvider, "generate", _generate(recorder)),
        (OpenAIProvider, "stream_chat", _stream_chat(recorder)),
        (OpenAITTSProvider, "generate_audio", _generate_audio(recorder)),
    ]
    originals = [(cls, name, getattr(cls, name)) for cls, name, _ in targets]
    for cls, name, fake in targets:
        setattr(cls, name, fake)

    def undo() -> None:
        for cls, name, original in originals:
            setattr(cls, name, original)

    return undo
