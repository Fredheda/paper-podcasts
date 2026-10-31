"""Structure checks for the deploy workflow, which cannot run offline.

They pin the ordering and secret handling the live gates would otherwise be the
only proof of.
"""

from conftest import REPO_ROOT

WORKFLOWS = REPO_ROOT / ".github" / "workflows"


def test_workflows_read_the_azure_ids_from_secrets_not_variables() -> None:
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        assert "vars.AZURE_" not in workflow.read_text(), workflow.name
    text = (WORKFLOWS / "deploy.yml").read_text()
    for secret in (
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_BUILD_CLIENT_ID",
        "AZURE_DEPLOY_CLIENT_ID",
    ):
        assert f"secrets.{secret}" in text, secret


def test_deploy_builds_the_validated_sha_as_the_build_identity_before_rolling() -> None:
    text = (WORKFLOWS / "deploy.yml").read_text()
    resolve = text.index("Resolve and validate")
    build_login = text.index("secrets.AZURE_BUILD_CLIENT_ID")
    build = text.index('./scripts/build-push.sh "$SHA"')
    deploy_login = text.index("secrets.AZURE_DEPLOY_CLIENT_ID")
    roll = text.index('./scripts/redeploy.sh "$SHA"')
    assert resolve < build_login < build < deploy_login < roll


def test_deploy_is_main_only_in_the_production_environment() -> None:
    text = (WORKFLOWS / "deploy.yml").read_text()
    assert "if: github.ref == 'refs/heads/main'" in text
    assert "environment: production" in text
    assert "cancel-in-progress: false" in text
    # id-token is requested on the job only, never workflow-wide.
    assert text.count("id-token: write") == 1


def test_ci_builds_and_deploys_nothing() -> None:
    text = (WORKFLOWS / "ci.yml").read_text()
    assert "build-push.sh" not in text
    assert "AZURE_" not in text
