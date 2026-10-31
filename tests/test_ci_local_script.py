"""scripts/ci-local.sh must run every check ci.yml runs, in the same order.

The only thing that catches a check added to ci.yml but forgotten in the local
script (which would let a PR pass locally and fail in CI).
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = re.compile(r"^(poetry (?:install|run) .+|npm (?:ci|run|test)\b.*)$")


def checks_in_workflow() -> list[str]:
    commands: list[str] = []
    for line in (ROOT / ".github/workflows/ci.yml").read_text().splitlines():
        match = re.match(r"\s*- run: (.+)", line)
        if match and CHECK.match(match.group(1).strip()):
            commands.append(match.group(1).strip())
    # Two jobs each run `npm ci`; the local script installs once.
    return list(dict.fromkeys(commands))


def checks_in_script() -> list[str]:
    return [
        line.strip()
        for line in (ROOT / "scripts/ci-local.sh").read_text().splitlines()
        if CHECK.match(line.strip())
    ]


def test_local_script_runs_every_ci_check_in_order() -> None:
    assert checks_in_workflow(), "no checks parsed from ci.yml"
    assert checks_in_script() == checks_in_workflow()
