"""Pins .github/rulesets/main-protect.json to the real workflow job ids.

A required check whose job was renamed never reports, and then no PR can
merge. These tests fail in that PR instead.
"""

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RULESET = ROOT / ".github" / "rulesets" / "main-protect.json"
WORKFLOWS = ROOT / ".github" / "workflows"
REQUIRED = {
    "backend",
    "frontend",
    "frontend-build",
    "gitleaks",
    "workflow-lint",
    "bandit",
}
# Advisory by design, or helpers: never block a merge.
ADVISORY = {"pip-audit", "npm-audit", "codeql", "review", "changes"}


def ruleset() -> dict[str, Any]:
    return json.loads(RULESET.read_text())


def rules() -> dict[str, dict[str, Any]]:
    return {rule["type"]: rule for rule in ruleset()["rules"]}


def required_contexts() -> list[str]:
    checks = rules()["required_status_checks"]["parameters"]["required_status_checks"]
    return [check["context"] for check in checks]


def job_ids(workflow: str) -> set[str]:
    """Return the top-level job ids (two-space indent under `jobs:`)."""
    text = (WORKFLOWS / workflow).read_text()
    jobs = text.split("\njobs:\n", 1)[1]
    return set(re.findall(r"^  ([\w-]+):\s*$", jobs, re.M))


def test_file_is_a_clean_put_body() -> None:
    allowed = {
        "name",
        "target",
        "enforcement",
        "conditions",
        "bypass_actors",
        "rules",
    }
    assert set(ruleset()) <= allowed


def test_keeps_existing_protections() -> None:
    body = ruleset()
    assert body["name"] == "main-protect"
    assert body["enforcement"] == "active"
    assert body["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert set(rules()) == {
        "deletion",
        "non_fast_forward",
        "pull_request",
        "required_status_checks",
    }
    assert rules()["pull_request"]["parameters"]["required_approving_review_count"] == 0
    assert body["bypass_actors"] == [
        {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "pull_request"}
    ]


def test_required_checks_are_exactly_the_agreed_six() -> None:
    contexts = required_contexts()
    assert len(contexts) == len(set(contexts))
    assert set(contexts) == REQUIRED
    params = rules()["required_status_checks"]["parameters"]
    assert params["strict_required_status_checks_policy"] is False
    assert params["do_not_enforce_on_create"] is False


def test_every_required_check_is_a_workflow_job() -> None:
    jobs = job_ids("ci.yml") | job_ids("security.yml")
    assert REQUIRED <= jobs, sorted(REQUIRED - jobs)


def test_advisory_jobs_are_not_required() -> None:
    assert not (set(required_contexts()) & ADVISORY)
