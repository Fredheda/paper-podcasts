"""The e2e backend: the real app with scripted fakes and isolated storage."""

import inspect
import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from backend.app import config
from backend.app import state as app_state
from backend.app.main import app as production_app
from src.services.arxiv_service import ArxivService
from src.services.llm_providers import OpenAIProvider
from src.services.tts_providers import OpenAITTSProvider
from tests.e2e_backend.launcher import e2e_backend

REPO_ROOT = Path(__file__).resolve().parents[2]
TEST_ROUTES = {"/__reset", "/__requests", "/__gate/release"}
PATCHED = [
    (ArxivService, "search_by_topic"),
    (ArxivService, "download_paper"),
    (OpenAIProvider, "generate"),
    (OpenAIProvider, "stream_chat"),
    (OpenAITTSProvider, "generate_audio"),
]


def route_paths(app: Any) -> set[str]:
    return {getattr(route, "path", "") for route in app.routes}


def parameters(function: Any) -> list[tuple[str, Any, Any]]:
    return [
        (p.name, p.kind, p.default)
        for p in inspect.signature(function).parameters.values()
    ]


def snapshot(root: Path) -> dict[str, tuple[int, int]]:
    if not root.exists():
        return {}
    return {
        str(path): (path.stat().st_mtime_ns, path.stat().st_size)
        for path in root.rglob("*")
        if path.is_file()
    }


def wait_for(check: Any, seconds: float = 60.0) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.2)
    raise AssertionError("condition not met in time")


def test_production_app_has_no_test_routes(tmp_path: Path) -> None:
    assert not route_paths(production_app) & TEST_ROUTES
    with e2e_backend(tmp_path) as app:
        assert TEST_ROUTES <= route_paths(app)
        assert not route_paths(production_app) & TEST_ROUTES
    assert not route_paths(production_app) & TEST_ROUTES


def test_launcher_stays_out_of_the_image() -> None:
    ignored = (REPO_ROOT / ".dockerignore").read_text().splitlines()
    assert "tests" in ignored


def test_fakes_keep_the_real_signatures_and_are_undone(tmp_path: Path) -> None:
    originals = {(cls, name): getattr(cls, name) for cls, name in PATCHED}
    with e2e_backend(tmp_path):
        for (cls, name), original in originals.items():
            patched = getattr(cls, name)
            assert patched is not original, name
            assert parameters(patched) == parameters(original), name
    for (cls, name), original in originals.items():
        assert getattr(cls, name) is original, name


def test_refuses_azure_storage_before_patching_anything(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = ArxivService.search_by_topic
    monkeypatch.setattr(app_state, "STORAGE_BACKEND", "azure")
    with pytest.raises(RuntimeError, match="STORAGE_BACKEND=local"):
        with e2e_backend(tmp_path):
            pass
    assert ArxivService.search_by_topic is original


def test_pipeline_runs_through_the_api_without_touching_the_real_data_dir(
    tmp_path: Path,
) -> None:
    real_before = snapshot(config.DATA_DIR)
    real_existed = config.DATA_DIR.exists()
    with e2e_backend(tmp_path) as app, TestClient(app) as client:
        # Storage and database sit under the temp dir.
        metadata = app_state.state.metadata_service
        blobs = app_state.state.blob_service
        assert Path(metadata.db_path).is_relative_to(tmp_path)  # type: ignore[union-attr]
        assert Path(blobs.root_dir).is_relative_to(tmp_path)  # type: ignore[union-attr]

        found = client.post("/api/search", json={"query": "rag"}).json()["papers"]
        assert [p["arxiv_id"] for p in found] == [
            "2501.00001",
            "2501.00002",
            "2501.00003",
        ]
        assert client.post("/api/search", json={"query": "none"}).json() == {
            "papers": []
        }

        good, bad = found[0], found[2]
        queued = client.post("/api/jobs/enqueue", json={"papers": [good, bad]}).json()
        assert queued == {"queued_count": 2, "skipped_count": 0}
        again = client.post("/api/jobs/enqueue", json={"papers": [good]}).json()
        assert again["queued_count"] + again["skipped_count"] == 1

        def done() -> bool:
            counts = client.get("/api/jobs").json()["counts"]
            return counts["completed"] == 1 and counts["failed"] == 1

        wait_for(done)
        jobs = {j["arxiv_id"]: j for j in client.get("/api/jobs").json()["jobs"]}
        assert jobs["2501.00001"]["stage"] == "completed"
        assert jobs["2501.00003"]["stage"] == "failed"
        assert "Processing failed" in (jobs["2501.00003"]["error"] or "")

        library = client.get("/api/library").json()
        assert [item["arxiv_id"] for item in library if item["audio_url"]] == [
            "2501.00001"
        ]
        content = client.get("/api/library/2501.00001/content").json()
        assert "Scripted summary" in content["summary_text"]

        audio = client.get("/api/library/2501.00001/audio")
        assert audio.status_code == 200
        assert audio.content[:2] == b"\xff\xfb"
        ranged = client.get(
            "/api/library/2501.00001/audio", headers={"Range": "bytes=0-99"}
        )
        assert ranged.status_code == 206
        assert ranged.headers["content-range"].startswith("bytes 0-99/")

        chat = client.post(
            "/api/chat/stream",
            json={
                "arxiv_ids": ["2501.00001"],
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert chat.text.count("event: token") == 3
        assert "event: done" in chat.text
        logged = [r for r in client.get("/__requests").json() if r["kind"] == "chat"]
        assert "Scripted Paper One" in logged[0]["system"]

        assert client.post("/__reset").json() == {"ok": True}
        assert client.get("/api/jobs").json()["jobs"] == []
        assert client.get("/api/library").json() == []
        assert client.get("/__requests").json() == []
        assert list((tmp_path / "papers").iterdir()) == []

    assert snapshot(config.DATA_DIR) == real_before
    assert config.DATA_DIR.exists() == real_existed
