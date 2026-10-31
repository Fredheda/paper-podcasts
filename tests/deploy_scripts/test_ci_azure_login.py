from conftest import FakeAz

OIDC_ENV = {
    "AZURE_TENANT_ID": "tenant-1",
    "AZURE_SUBSCRIPTION_ID": "sub-1",
    "ACTIONS_ID_TOKEN_REQUEST_URL": "https://token.example.test/req?x=1",
    "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "request-secret",
}


def test_exchanges_the_github_token_for_an_azure_session(fake_az: FakeAz) -> None:
    result = fake_az.run("scripts/ci-azure-login.sh", "client-1", env=OIDC_ENV)
    assert result.returncode == 0, result.stderr
    (request,) = fake_az.curl_calls
    assert "audience=api://AzureADTokenExchange" in request
    assert any(
        c.startswith("login --service-principal")
        and "-u client-1" in c
        and "-t tenant-1" in c
        and "--federated-token fake-token" in c
        for c in fake_az.calls
    )
    assert "account set --subscription sub-1" in fake_az.calls
    assert "::add-mask::fake-token" in result.stdout


def test_needs_the_oidc_environment(fake_az: FakeAz) -> None:
    result = fake_az.run(
        "scripts/ci-azure-login.sh",
        "client-1",
        env={
            **OIDC_ENV,
            "ACTIONS_ID_TOKEN_REQUEST_URL": "",
            "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "",
        },
    )
    assert result.returncode == 1
    assert "id-token: write" in result.stderr
    assert fake_az.calls == []
