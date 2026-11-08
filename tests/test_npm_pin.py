"""Keeps the pinned npm version in step across the image and the CI jobs.

Dependabot does not see `npm install -g npm@X`, so drift would be silent.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "frontend" / "Dockerfile"
CI = ROOT / ".github" / "workflows" / "ci.yml"
SECURITY = ROOT / ".github" / "workflows" / "security.yml"
PIN = re.compile(r"npm install -g npm@(\d+\.\d+\.\d+) && npm --version")


def pins(path: Path) -> list[str]:
    return PIN.findall(path.read_text())


def count(path: Path, pattern: str) -> int:
    return len(re.findall(pattern, path.read_text(), flags=re.MULTILINE))


def test_one_npm_version_everywhere() -> None:
    versions = {v for path in (DOCKERFILE, CI, SECURITY) for v in pins(path)}
    assert len(versions) == 1, versions


def test_every_docker_stage_pins_npm() -> None:
    assert len(pins(DOCKERFILE)) == count(DOCKERFILE, r"^FROM ") >= 2


def test_every_node_job_pins_npm() -> None:
    for workflow in (CI, SECURITY):
        assert len(pins(workflow)) == count(workflow, r"uses: actions/setup-node@")
