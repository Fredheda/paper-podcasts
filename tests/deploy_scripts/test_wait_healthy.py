from conftest import FakeAz


def test_passes_once_every_revision_is_provisioned(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/wait-healthy.sh",
        "30",
        "0",
        env={"FAKE_PROVISIONING": "Provisioning,Provisioned"},
    )
    assert result.returncode == 0, result.stderr
    assert "ca-podcasts-agent" in result.stdout
    assert "ca-podcasts-web" in result.stdout


def test_fails_fast_on_a_failed_revision(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/wait-healthy.sh", "30", "0", env={"FAKE_PROVISIONING": "Failed"}
    )
    assert result.returncode == 1
    assert "failed to provision" in result.stderr


def test_times_out_when_a_revision_never_provisions(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/wait-healthy.sh", "1", "1", env={"FAKE_PROVISIONING": "Provisioning"}
    )
    assert result.returncode == 1
    assert "timed out" in result.stderr
