import shutil
import subprocess
from pathlib import Path

import pytest
from conftest import REPO_ROOT, FakeAz

SHA = "a" * 40


@pytest.mark.parametrize(
    "bad", ["abc", "A" * 40, "", "$(touch pwned)", f"{SHA} extra", "g" * 40]
)
def test_rejects_malformed_sha_before_any_az_call(fake_az: FakeAz, bad: str) -> None:
    result = fake_az.run("scripts/build-push.sh", bad)
    assert result.returncode != 0
    assert fake_az.calls == []


def test_rejects_a_sha_that_is_not_a_commit(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/build-push.sh", SHA)
    assert result.returncode != 0
    assert fake_az.calls == []


def _missing(sha: str) -> str:
    """FAKE_MISSING value: neither image exists in the registry for `sha`."""
    return f"podcasts-agent:{sha},podcasts-web:{sha}"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def two_commit_repo(tmp_path: Path) -> tuple[Path, str, str]:
    """A repo holding the real scripts, then a second commit that changes files."""
    repo = tmp_path / "repo"
    (repo / "scripts" / "lib").mkdir(parents=True)
    for rel in ("scripts/build-push.sh", "scripts/lib/images.sh"):
        shutil.copy(REPO_ROOT / rel, repo / rel)
    _git(repo, "init", "-q")
    (repo / "only_in_first.txt").write_text("1")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "first")
    first = _git(repo, "rev-parse", "HEAD")
    (repo / "only_in_first.txt").unlink()
    (repo / "only_in_second.txt").write_text("2")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "second")
    return repo, first, _git(repo, "rev-parse", "HEAD")


def test_builds_the_requested_commit_not_the_working_tree(
    fake_az: FakeAz, two_commit_repo: tuple[Path, str, str]
) -> None:
    repo, first, _ = two_commit_repo
    result = fake_az.run(
        "scripts/build-push.sh",
        first,
        env={"FAKE_MISSING": _missing(first)},
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    contexts = "\n".join(fake_az.build_contexts)
    assert "only_in_first.txt" in contexts
    assert "only_in_second.txt" not in contexts
    assert str(repo) not in contexts  # built from a temporary archive


def test_builds_both_images_when_none_exist(
    fake_az: FakeAz, two_commit_repo: tuple[Path, str, str]
) -> None:
    repo, _, head = two_commit_repo
    result = fake_az.run(
        "scripts/build-push.sh",  # default: HEAD
        env={"FAKE_MISSING": _missing(head)},
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    builds = [c for c in fake_az.calls if c.startswith("acr build")]
    assert len(builds) == 2
    assert f"--image podcasts-agent:latest --image podcasts-agent:{head}" in builds[0]
    assert f"--image podcasts-web:latest --image podcasts-web:{head}" in builds[1]


def test_skips_images_that_already_exist(
    fake_az: FakeAz, two_commit_repo: tuple[Path, str, str]
) -> None:
    repo, _, head = two_commit_repo
    result = fake_az.run("scripts/build-push.sh", head, cwd=repo)
    assert result.returncode == 0, result.stderr
    assert [c for c in fake_az.calls if c.startswith("acr build")] == []
    assert "Nothing to build" in result.stdout


def test_builds_only_the_missing_image(
    fake_az: FakeAz, two_commit_repo: tuple[Path, str, str]
) -> None:
    repo, _, head = two_commit_repo
    result = fake_az.run(
        "scripts/build-push.sh",
        head,
        env={"FAKE_MISSING": f"podcasts-web:{head}"},
        cwd=repo,
    )
    assert result.returncode == 0, result.stderr
    builds = [c for c in fake_az.calls if c.startswith("acr build")]
    assert len(builds) == 1
    assert f"podcasts-web:{head}" in builds[0]


def test_a_failed_build_stops_before_the_next_image(
    fake_az: FakeAz, two_commit_repo: tuple[Path, str, str]
) -> None:
    repo, _, head = two_commit_repo
    result = fake_az.run(
        "scripts/build-push.sh",
        head,
        env={"FAKE_MISSING": _missing(head), "FAKE_FAIL_BUILD": "podcasts-agent"},
        cwd=repo,
    )
    assert result.returncode != 0
    builds = [c for c in fake_az.calls if c.startswith("acr build")]
    assert len(builds) == 1
    assert "podcasts-agent" in builds[0]
