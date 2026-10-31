import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import REPO_ROOT, FakeAz


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "scripts" / "lib").mkdir(parents=True)
    for rel in (
        "scripts/ship.sh",
        "scripts/build-push.sh",
        "scripts/redeploy.sh",
        "scripts/lib/images.sh",
    ):
        shutil.copy(REPO_ROOT / rel, root / rel)
    _git(root, "init", "-q")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "scripts")
    return root


def test_ship_refuses_a_dirty_tree(fake_az: FakeAz, repo: Path) -> None:
    (repo / "dirty.txt").write_text("x")
    result = fake_az.run("scripts/ship.sh", cwd=repo)
    assert result.returncode == 1
    assert "dirty" in result.stderr
    assert fake_az.calls == []


def test_ship_builds_missing_images_then_rolls_the_apps(
    fake_az: FakeAz, repo: Path
) -> None:
    head = _git(repo, "rev-parse", "HEAD")
    result = fake_az.run(
        "scripts/ship.sh",
        env={"FAKE_MISSING": f"podcasts-agent:{head},podcasts-web:{head}"},
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    verbs = [c.split()[0:2] for c in fake_az.calls]
    first_update = verbs.index(["containerapp", "update"])
    assert ["acr", "build"] in verbs[:first_update]
