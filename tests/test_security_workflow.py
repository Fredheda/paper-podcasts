"""Structure checks for security.yml, which cannot run offline.

They pin what the required-checks ruleset and the Actions allowlist depend on:
stable job ids, GitHub-owned actions only, pinned images, least privilege.
"""

import re
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parents[1] / ".github" / "workflows" / "security.yml"
)
JOBS = ("gitleaks", "workflow-lint", "pip-audit", "npm-audit", "bandit", "codeql")


def text() -> str:
    return WORKFLOW.read_text()


def job_block(job: str) -> str:
    """Return the text of one top-level job (two-space indent) of the workflow."""
    match = re.search(rf"^  {re.escape(job)}:\n(.*?)(?=^  \S|\Z)", text(), re.M | re.S)
    assert match, f"job {job} missing"
    return match.group(1)


def test_job_ids_are_stable() -> None:
    for job in JOBS:
        job_block(job)


def test_only_github_owned_actions() -> None:
    uses = re.findall(r"uses:\s*(\S+)", text())
    assert uses, "no actions used"
    for action in uses:
        assert action.startswith(("actions/", "github/")), action


def test_docker_images_are_pinned() -> None:
    images = re.findall(r"(ghcr\.io/gitleaks/gitleaks|rhysd/actionlint):(\S+)", text())
    assert {name for name, _ in images} == {
        "ghcr.io/gitleaks/gitleaks",
        "rhysd/actionlint",
    }
    for name, tag in images:
        assert re.fullmatch(r"v?\d+\.\d+\.\d+", tag), f"{name}:{tag}"


def test_least_privilege() -> None:
    body = text()
    assert re.search(r"^permissions:\n  contents: read\n", body, re.M)
    # security-events is requested by the codeql job only.
    assert body.count("security-events: write") == 1
    assert "security-events: write" in job_block("codeql")


def test_blocking_jobs_also_run_on_drafts() -> None:
    for job in ("gitleaks", "workflow-lint"):
        assert "draft" not in job_block(job), job
        assert "continue-on-error" not in job_block(job), job


def test_scans_wait_for_ready_prs() -> None:
    for job in ("pip-audit", "npm-audit", "bandit", "codeql"):
        assert "!github.event.pull_request.draft" in job_block(job), job


def test_dependency_audits_are_advisory_on_prs_only() -> None:
    for job in ("pip-audit", "npm-audit"):
        assert (
            "continue-on-error: ${{ github.event_name == 'pull_request' }}"
            in job_block(job)
        ), job


def test_scan_scope_and_severity() -> None:
    assert "--omit=dev" in job_block("npm-audit")
    assert "--audit-level=high" in job_block("npm-audit")
    assert "working-directory: frontend" in job_block("npm-audit")
    bandit = job_block("bandit")
    assert "-lll" in bandit
    for path in ("src", "backend", "scripts"):
        assert re.search(rf"\b{path}\b", bandit), path
    assert "javascript-typescript" in job_block("codeql")
    assert "python" in job_block("codeql")


def test_pull_requests_scan_only_their_commits_with_gitleaks() -> None:
    body = job_block("gitleaks")
    assert "fetch-depth: 0" in body
    assert "--log-opts" in body
    assert "--redact" in body


def test_runs_on_pull_requests_and_weekly_never_on_push() -> None:
    body = text()
    assert "pull_request:" in body
    assert "schedule:" in body
    assert "workflow_dispatch:" in body
    assert not re.search(r"^  push:", body, re.M)
