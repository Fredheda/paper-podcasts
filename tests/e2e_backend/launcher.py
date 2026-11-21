"""Run the real backend app with scripted fakes, for the browser suite.

`python -m tests.e2e_backend.launcher` serves it on 127.0.0.1:$E2E_BACKEND_PORT
(default 8100) with storage in a temp directory. The production app object
(`backend.app.main.app`) is never changed: the test routes live on a second
app built here.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from .fakes import Recorder, install_fakes

DEFAULT_PORT = 8100


def _add_test_routes(app: FastAPI, data_dir: Path, recorder: Recorder) -> None:
    @app.post("/__reset")
    def reset() -> dict[str, bool]:
        """Forget every paper, job and logged request."""
        from backend.app.config import DEFAULT_MAX_CONCURRENT
        from backend.app.state import state
        from src.services.processing_manager import ProcessingManager

        # Release a held summary or chat stream first, then wait for the old
        # workers: shutdown() joins each for only 2 s, and one that outlives the
        # reset would write its paper into the fresh storage.
        recorder.gate.set()
        if state.processing is not None:
            state.processing.shutdown()
            for worker in state.processing._workers:
                worker.join(timeout=15.0)
        papers = data_dir / "papers"
        if papers.exists():
            for child in papers.iterdir():
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
        database = data_dir / "podcasts.db"
        if database.exists():
            connection = sqlite3.connect(database)
            try:
                connection.execute("DELETE FROM papers")
                connection.commit()
            finally:
                connection.close()
        if state.pipeline is not None:
            state.processing = ProcessingManager(
                state.pipeline, max_concurrent=DEFAULT_MAX_CONCURRENT
            )
        recorder.reset()
        return {"ok": True}

    @app.get("/__requests")
    def requests() -> list[dict[str, Any]]:
        """What the fakes received since the last reset."""
        return recorder.requests()

    @app.post("/__gate/release")
    def release_gate() -> dict[str, bool]:
        """Let a held chat stream or HOLD summary continue."""
        recorder.gate.set()
        return {"ok": True}


@contextmanager
def e2e_backend(data_dir: Path) -> Iterator[FastAPI]:
    """Yield a backend app with fakes installed and storage under `data_dir`.

    Patches are undone on exit. Refuses to run against Azure storage.
    """
    from backend.app import state as app_state
    from backend.app.main import create_app

    if app_state.STORAGE_BACKEND != "local":
        raise RuntimeError("The e2e backend needs STORAGE_BACKEND=local.")
    recorder = Recorder()
    previous_data_dir = app_state.DATA_DIR
    app_state.DATA_DIR = data_dir
    undo = install_fakes(recorder)
    try:
        app = create_app()
        _add_test_routes(app, data_dir, recorder)
        yield app
    finally:
        undo()
        app_state.DATA_DIR = previous_data_dir


def main() -> None:
    # Before the first backend import: security.py reads these at import time.
    os.environ["OPENAI_API_KEY"] = "e2e-not-a-key"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"
    for name in ("BACKEND_API_KEY", "FORCE_HTTPS", "TRUST_PROXY_HEADERS"):
        os.environ.pop(name, None)

    import uvicorn

    port = int(os.environ.get("E2E_BACKEND_PORT", DEFAULT_PORT))
    with tempfile.TemporaryDirectory(prefix="pp-e2e-") as tmp:
        with e2e_backend(Path(tmp)) as app:
            uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
