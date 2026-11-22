"""Supply-chain rules of this repo, checked offline.

1. A 14-day install cooldown for npm and Poetry, with no exclusion committed.
2. No pip or pipx install without an exact version; one Poetry version.
3. Every GitHub Action pinned by commit, with its release as a comment.
4. Every Docker image (Dockerfile `FROM`, workflow `docker run`) pinned by
   `@sha256` digest, one digest per base image per Dockerfile.

To bump Poetry or pip, change the version in every workflow and in
backend/Dockerfile together; Dependabot does not see these pins.
"""

import re
import shlex
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
INSTALL = re.compile(r"\b(?:pip|pipx) (?:install|inject)\b")
POETRY_PIN = re.compile(r"poetry==(\d+\.\d+\.\d+)")
NPX_YES = re.compile(r"\bnpx\s+(?:-y|--yes)(?!\w)")
USES = re.compile(r"^\s*(?:-\s+)?uses:\s+(\S+)(?:\s+#\s*(\S+))?")
COMMIT_PIN = re.compile(r"[\w./-]+@[0-9a-f]{40}")
RELEASE = re.compile(r"v\d\S*")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}$")
STAGE = re.compile(r"^FROM\s+(\S+)(?:\s+AS\s+(\S+))?", re.M | re.I)
DOCKER_RUN_VALUE_FLAGS = {
    "-v",
    "--volume",
    "-w",
    "--workdir",
    "-e",
    "--env",
    "-u",
    "--user",
    "--entrypoint",
    "--name",
    "-p",
    "--publish",
}


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


def test_no_tool_is_pip_installed_into_the_project_environment() -> None:
    found = [
        f"{where}: {text}"
        for where, text in code_lines(WORKFLOWS)
        if "poetry run pip install" in text
    ]
    assert not found, found


def dockerfile_bases(dockerfile: Path) -> list[str]:
    """Return the base images of a Dockerfile's stages, without stage aliases."""
    stages = STAGE.findall(dockerfile.read_text())
    aliases = {alias.lower() for _, alias in stages if alias}
    return [image for image, _ in stages if image.lower() not in aliases]


def docker_run_images(workflows: Iterable[Path]) -> Iterator[tuple[str, str]]:
    """Yield (location, image) for every `docker run` in the workflows."""
    for where, text in code_lines(workflows):
        if "docker run" not in text:
            continue
        tokens = shlex.split(text.rstrip("\\"))
        i = tokens.index("run") + 1
        while tokens[i].startswith("-"):
            i += 2 if tokens[i] in DOCKER_RUN_VALUE_FLAGS else 1
        yield where, tokens[i]


def test_every_dockerfile_base_image_is_pinned_by_digest() -> None:
    unpinned = [
        f"{dockerfile.relative_to(ROOT)}: {image}"
        for dockerfile in tracked("Dockerfile")
        for image in dockerfile_bases(dockerfile)
        if not DIGEST.search(image)
    ]
    assert not unpinned, unpinned


def test_every_docker_run_image_is_pinned_by_digest() -> None:
    unpinned = [
        f"{where}: {image}"
        for where, image in docker_run_images(WORKFLOWS)
        if not DIGEST.search(image)
    ]
    assert not unpinned, unpinned


def test_one_digest_per_base_image_in_a_dockerfile() -> None:
    for dockerfile in tracked("Dockerfile"):
        digests: dict[str, set[str]] = {}
        for image in dockerfile_bases(dockerfile):
            name, _, digest = image.partition("@")
            digests.setdefault(name, set()).add(digest)
        assert all(len(found) == 1 for found in digests.values()), (dockerfile, digests)
