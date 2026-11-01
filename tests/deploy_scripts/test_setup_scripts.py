import json
from pathlib import Path

from conftest import FakeAz

SHA = "c" * 40
REGISTRY = "acrchatbotfredheda.azurecr.io"
REPOS = ("podcasts-agent", "podcasts-web")


def _command(fake_az: FakeAz, prefix: str) -> str:
    (call,) = [c for c in fake_az.calls if c.startswith(prefix)]
    return call


def test_build_identity_never_gets_container_apps_contributor(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/setup-github-deploy.sh")
    assert result.returncode == 0, result.stderr
    roles = [c for c in fake_az.calls if c.startswith("role assignment create")]
    build = [c for c in roles if "principal-id-podcasts-gh-build" in c]
    deploy = [c for c in roles if "principal-id-podcasts-gh-deploy" in c]
    assert {r for c in build for r in ("AcrPush", "Tasks Contributor") if r in c} == {
        "AcrPush",
        "Tasks Contributor",
    }
    assert len(build) == 2  # the two registry roles and nothing else
    assert not any("Container Apps Contributor" in c for c in build)
    assert sum("Container Apps Contributor" in c for c in deploy) == 2  # one per app


def test_both_federated_credentials_trust_only_the_production_environment(
    fake_az: FakeAz,
) -> None:
    result = fake_az.run("scripts/setup-github-deploy.sh")
    assert result.returncode == 0, result.stderr
    creds = [
        c for c in fake_az.calls if c.startswith("identity federated-credential create")
    ]
    assert len(creds) == 2
    for call in creds:
        assert "--subject repo:Fredheda/paper-podcasts:environment:production" in call
        assert "refs/heads" not in call


def _environment_body(fake_az: FakeAz) -> dict[str, object]:
    """The JSON the script sends to `PUT .../environments/production`."""
    return json.loads(Path(f"{fake_az.log}.gh-body").read_text())


def test_production_environment_admits_only_main(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/setup-github-deploy.sh")
    assert result.returncode == 0, result.stderr
    assert _environment_body(fake_az)["deployment_branch_policy"] == {
        "protected_branches": False,
        "custom_branch_policies": True,
    }
    assert any("-X POST" in c and "name=main" in c for c in fake_az.gh_calls)

    again = fake_az.run(
        "scripts/setup-github-deploy.sh", env={"FAKE_POLICY_NAMES": "main"}
    )
    assert again.returncode == 0, again.stderr
    posts = [c for c in fake_az.gh_calls if "-X POST" in c]
    assert len(posts) == 1  # the second run found the policy and added nothing


def test_production_environment_requires_the_repo_owner_as_reviewer(
    fake_az: FakeAz,
) -> None:
    # Every deploy then waits for the owner's approval in GitHub, and no admin
    # can bypass the gate.
    result = fake_az.run("scripts/setup-github-deploy.sh")
    assert result.returncode == 0, result.stderr
    assert "api users/Fredheda --jq .id" in fake_az.gh_calls
    body = _environment_body(fake_az)
    assert body["reviewers"] == [{"type": "User", "id": 77542239}]
    assert body["prevent_self_review"] is False
    assert body["can_admins_bypass"] is False


def test_azure_ids_are_stored_as_secrets_not_variables(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/setup-github-deploy.sh")
    assert result.returncode == 0, result.stderr
    for name in (
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_BUILD_CLIENT_ID",
        "AZURE_DEPLOY_CLIENT_ID",
    ):
        assert any(
            c.startswith(f"secret set {name} --body ")
            and c.endswith(" -R Fredheda/paper-podcasts")
            for c in fake_az.gh_calls
        ), name
    assert not any("variable set" in c for c in fake_az.gh_calls)


def test_purge_locks_running_tags_before_the_dry_run(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/setup-acr-purge.sh",
        env={
            "FAKE_IMAGE_CA_PODCASTS_AGENT": f"{REGISTRY}/podcasts-agent:{SHA}",
            "FAKE_IMAGE_CA_PODCASTS_WEB": f"{REGISTRY}/podcasts-web:latest",
        },
    )
    assert result.returncode == 0, result.stderr
    locks = [c for c in fake_az.calls if c.startswith("acr repository update")]
    assert len(locks) == 1  # the app on :latest is not locked
    assert f"podcasts-agent:{SHA}" in locks[0] and "--delete-enabled false" in locks[0]
    lock_at = fake_az.calls.index(locks[0])
    dry_at = fake_az.calls.index(_command(fake_az, "acr run"))
    assert lock_at < dry_at
    assert not any(c.startswith("acr task create") for c in fake_az.calls)


def test_purge_filters_name_only_the_two_sha_tag_patterns(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/setup-acr-purge.sh")
    assert result.returncode == 0, result.stderr
    run_call = _command(fake_az, "acr run")
    assert run_call.count("--filter") == 2
    for repo in REPOS:
        assert f"--filter '{repo}:^[0-9a-f]{{40}}$'" in run_call
    for needed in ("--ago 30d", "--keep 10", "--untagged", "--dry-run"):
        assert needed in run_call
    assert "--include-locked" not in run_call


def test_purge_create_makes_a_weekly_task_without_dry_run(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/setup-acr-purge.sh", "--create", env={"FAKE_NO_TASK": "1"}
    )
    assert result.returncode == 0, result.stderr
    create = _command(fake_az, "acr task create")
    assert "-n purge-podcasts-images" in create
    assert "--schedule 0 3 * * Sun" in create
    assert "--dry-run" not in create
    assert "--include-locked" not in create
    assert create.count("--filter") == 2


def test_purge_create_replaces_an_existing_task(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/setup-acr-purge.sh", "--create")
    assert result.returncode == 0, result.stderr
    verbs = [c.split()[2] for c in fake_az.calls if c.startswith("acr task ")]
    assert verbs == ["show", "delete", "create"]
