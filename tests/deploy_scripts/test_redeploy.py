import pytest
from conftest import FakeAz

SHA = "a" * 40
OLD = "b" * 40
REGISTRY = "acrchatbotfredheda.azurecr.io"


@pytest.mark.parametrize(
    "bad", ["abc", "A" * 40, "", "$(touch pwned)", f"{SHA} extra", "g" * 40]
)
def test_rejects_malformed_sha_before_any_az_call(fake_az: FakeAz, bad: str) -> None:
    result = fake_az.run("scripts/redeploy.sh", bad)
    assert result.returncode == 2
    assert fake_az.calls == []


def test_a_missing_image_changes_nothing(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/redeploy.sh", SHA, env={"FAKE_MISSING": f"podcasts-web:{SHA}"}
    )
    assert result.returncode == 1
    assert "podcasts-web" in result.stderr
    assert not [c for c in fake_az.calls if c.startswith("containerapp update")]
    assert not [c for c in fake_az.calls if c.startswith("acr repository update")]


def test_rolls_both_apps_in_order(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/redeploy.sh", SHA)
    assert result.returncode == 0, result.stderr
    updates = [c for c in fake_az.calls if c.startswith("containerapp update")]
    assert len(updates) == 2
    assert "-n ca-podcasts-agent" in updates[0]
    assert f"--image {REGISTRY}/podcasts-agent:{SHA}" in updates[0]
    assert "-n ca-podcasts-web" in updates[1]
    assert f"--image {REGISTRY}/podcasts-web:{SHA}" in updates[1]


def test_locks_new_tags_and_unlocks_replaced_ones(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/redeploy.sh",
        SHA,
        env={
            "FAKE_IMAGE_CA_PODCASTS_AGENT": f"{REGISTRY}/podcasts-agent:{OLD}",
            "FAKE_IMAGE_CA_PODCASTS_WEB": f"{REGISTRY}/podcasts-web:{OLD}",
        },
    )
    assert result.returncode == 0, result.stderr
    locks = [c for c in fake_az.calls if c.startswith("acr repository update")]
    for repo in ("podcasts-agent", "podcasts-web"):
        assert any(
            f"--image {repo}:{SHA}" in c and "--delete-enabled false" in c
            for c in locks
        )
        assert any(
            f"--image {repo}:{OLD}" in c and "--delete-enabled true" in c for c in locks
        )


def test_never_touches_latest_or_unlocks_the_sha_it_is_on(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/redeploy.sh",
        SHA,
        env={
            "FAKE_IMAGE_CA_PODCASTS_AGENT": f"{REGISTRY}/podcasts-agent:{SHA}",
            "FAKE_IMAGE_CA_PODCASTS_WEB": f"{REGISTRY}/podcasts-web:latest",
        },
    )
    assert result.returncode == 0, result.stderr
    unlocks = [c for c in fake_az.calls if "--delete-enabled true" in c]
    assert unlocks == []
    assert not [c for c in fake_az.calls if ":latest" in c and "repository update" in c]


def test_a_failed_rollout_changes_no_lock(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/redeploy.sh", SHA, env={"FAKE_FAIL_UPDATE": "ca-podcasts-web"}
    )
    assert result.returncode != 0
    assert not [c for c in fake_az.calls if c.startswith("acr repository update")]
