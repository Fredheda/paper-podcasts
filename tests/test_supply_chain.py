"""Supply-chain rules of this repo, checked offline.

1. A 14-day install cooldown for npm and Poetry, with no exclusion committed.
2. No pip or pipx install without an exact version; one Poetry version.
3. Every GitHub Action pinned by commit, with its release as a comment.

To bump Poetry or pip, change the version in every workflow and in
backend/Dockerfile together; Dependabot does not see these pins.
"""

import re
import subprocess
from collections.abc import Iterable, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
DOCKERFILE = ROOT / "backend" / "Dockerfile"
INSTALL_SOURCES = [
    *WORKFLOWS,
    ROOT / "scripts" / "ci-local.sh",
    DOCKERFILE,
    ROOT / "frontend" / "Dockerfile",
]
INSTALL = re.compile(r"\b(?:pip|pipx) install\b")
POETRY_PIN = re.compile(r"poetry==(\d+\.\d+\.\d+)")
NPX_YES = re.compile(r"\bnpx\s+(?:-y|--yes)(?!\w)")
USES = re.compile(r"^\s*(?:-\s+)?uses:\s+(\S+)(?:\s+#\s*(\S+))?")
COMMIT_PIN = re.compile(r"[\w./-]+@[0-9a-f]{40}")
RELEASE = re.compile(r"v\d\S*")


def tracked(name: str) -> list[Path]:
    """Return the tracked files called `name`, wherever they sit."""
    out = subprocess.run(
        ["git", "ls-files", f"*{name}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [ROOT / line for line in out.splitlines() if Path(line).name == name]


def code_lines(paths: Iterable[Path]) -> Iterator[tuple[str, str]]:
    """Yield (location, text) for every line that is not a full-line comment."""
    for path in paths:
        for number, text in enumerate(path.read_text().splitlines(), 1):
            if not text.lstrip().startswith("#"):
                yield f"{path.relative_to(ROOT)}:{number}", text.strip()


def test_every_manifest_has_the_cooldown() -> None:
    for manifest in tracked("package.json"):
        npmrc = manifest.parent / ".npmrc"
        assert npmrc.is_file(), npmrc
        assert "min-release-age=14" in npmrc.read_text().splitlines(), npmrc
    for manifest in tracked("pyproject.toml"):
        poetry_toml = manifest.parent / "poetry.toml"
        assert poetry_toml.is_file(), poetry_toml
        lines = poetry_toml.read_text().splitlines()
        assert "[solver]" in lines, poetry_toml
        assert "min-release-age = 14" in lines, poetry_toml


def test_no_cooldown_exclusion_is_committed() -> None:
    for name in (".npmrc", "poetry.toml"):
        for path in tracked(name):
            assert "min-release-age-exclude" not in path.read_text(), path


def test_pip_and_pipx_installs_are_exact() -> None:
    loose = [
        f"{where}: {text}"
        for where, text in code_lines(INSTALL_SOURCES)
        if INSTALL.search(text) and "==" not in text
    ]
    assert not loose, loose


def test_one_poetry_version_everywhere() -> None:
    versions = {
        version
        for path in [*WORKFLOWS, DOCKERFILE]
        for version in POETRY_PIN.findall(path.read_text())
    }
    assert len(versions) == 1, versions


def test_dockerfile_installs_poetry_with_the_pip_cooldown() -> None:
    text = DOCKERFILE.read_text()
    assert re.search(r"pip install --no-cache-dir pip==\d", text)
    assert "PIP_UPLOADED_PRIOR_TO=P14D pip install" in text


def test_no_npx_yes() -> None:
    sources = [*WORKFLOWS, ROOT / "scripts" / "ci-local.sh"]
    found = [
        f"{where}: {text}"
        for where, text in code_lines(sources)
        if NPX_YES.search(text)
    ]
    assert not found, found


def test_every_action_is_pinned_by_commit() -> None:
    unpinned = []
    for where, text in code_lines(WORKFLOWS):
        match = USES.match(text)
        if not match or match.group(1).startswith("./"):
            continue
        action, release = match.group(1), match.group(2) or ""
        if not COMMIT_PIN.fullmatch(action) or not RELEASE.fullmatch(release):
            unpinned.append(f"{where}: {text}")
    assert not unpinned, unpinned
