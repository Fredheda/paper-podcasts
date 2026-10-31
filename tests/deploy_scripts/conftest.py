"""Fake `az`, `curl` and `gh` on PATH for the deploy-script tests.

The fake `az` records every call (one line of arguments) and answers from
environment variables, so the tests can check what a script would do to Azure
without touching it:

- FAKE_MISSING: comma list of `repo:tag`; `az acr repository show` exits 1 for them.
- FAKE_FAIL_BUILD: repository whose `az acr build` exits 1.
- FAKE_FAIL_UPDATE: container app whose `az containerapp update` exits 1.
- FAKE_IMAGE_<APP>: image printed for `containerapp show ... image` (app name
  upper-cased, `-` replaced by `_`).
- FAKE_NO_TASK: when set, `az acr task show` exits 1 (no purge task yet).
- FAKE_PROVISIONING: comma list of revision states, one per
  `containerapp revision show` call (the last value repeats).
- FAKE_POLICY_NAMES: branch policy names `gh api .../deployment-branch-policies` prints.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

FAKE_AZ = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$*" in
  "acr build"*)
    repo=$(echo "$*" | sed -E 's/.*--image ([^: ]+):latest.*/\1/')
    # Record where the build ran from and what the context holds.
    { echo "PWD=$PWD"; ls -A "${@: -1}"; } >> "$FAKE_LOG.ctx"
    [ "$repo" = "${FAKE_FAIL_BUILD:-}" ] && exit 1
    exit 0 ;;
  "acr repository show"*)
    image=$(echo "$*" | sed -E 's/.*--image ([^ ]+).*/\1/')
    case ",${FAKE_MISSING:-}," in *",$image,"*) exit 1 ;; esac
    exit 0 ;;
  "containerapp update"*)
    app=$(echo "$*" | sed -E 's/.*-n ([^ ]+).*/\1/')
    [ "$app" = "${FAKE_FAIL_UPDATE:-}" ] && exit 1
    exit 0 ;;
  "containerapp show"*latestRevisionName*)
    app=$(echo "$*" | sed -E 's/.*-n ([^ ]+).*/\1/')
    echo "$app--rev1"; exit 0 ;;
  "containerapp show"*ingress.fqdn*)
    echo "web.example.test"; exit 0 ;;
  "containerapp show"*image*)
    app=$(echo "$*" | sed -E 's/.*-n ([^ ]+).*/\1/')
    var="FAKE_IMAGE_$(echo "$app" | tr 'a-z-' 'A-Z_')"
    echo "${!var:-}"; exit 0 ;;
  "acr task show"*)
    [ -n "${FAKE_NO_TASK:-}" ] && exit 1
    exit 0 ;;
  "containerapp revision show"*)
    counter="$FAKE_LOG.provisioning"
    n=$(cat "$counter" 2>/dev/null || echo 0)
    IFS=',' read -r -a states <<< "${FAKE_PROVISIONING:-Provisioned}"
    last=$(( ${#states[@]} - 1 ))
    idx=$(( n > last ? last : n ))
    echo "${states[$idx]}"
    echo $(( n + 1 )) > "$counter"
    exit 0 ;;
esac
exit 0
"""

# Stands in for the GitHub Actions OIDC token endpoint.
FAKE_CURL = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG.curl"
echo '{"value":"fake-token"}'
"""

# Stands in for the GitHub CLI. Listing the environment's branch policies
# prints the names in FAKE_POLICY_NAMES, as the script's --jq filter would.
FAKE_GH = r"""#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG.gh"
case "$*" in
  *"deployment-branch-policies"*)
    case "$*" in *"-X POST"*) exit 0 ;; esac
    printf '%s' "${FAKE_POLICY_NAMES:-}"
    exit 0 ;;
esac
exit 0
"""


@dataclass
class FakeAz:
    log: Path
    bin_dir: Path

    def run(
        self,
        script: str,
        *args: str,
        env: dict[str, str] | None = None,
        cwd: Path = REPO_ROOT,
    ) -> subprocess.CompletedProcess[str]:
        full_env = {
            **os.environ,
            "PATH": f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}",
            "FAKE_LOG": str(self.log),
            **(env or {}),
        }
        return subprocess.run(
            ["bash", script, *args],
            cwd=cwd,
            env=full_env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _read(self, suffix: str) -> list[str]:
        path = Path(f"{self.log}{suffix}")
        return path.read_text().splitlines() if path.exists() else []

    @property
    def calls(self) -> list[str]:
        return self._read("")

    @property
    def gh_calls(self) -> list[str]:
        return self._read(".gh")

    @property
    def curl_calls(self) -> list[str]:
        return self._read(".curl")

    @property
    def build_contexts(self) -> list[str]:
        return self._read(".ctx")


@pytest.fixture
def fake_az(tmp_path: Path) -> FakeAz:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("az", FAKE_AZ), ("curl", FAKE_CURL), ("gh", FAKE_GH)):
        tool = bin_dir / name
        tool.write_text(body)
        tool.chmod(0o755)
    return FakeAz(log=tmp_path / "az.log", bin_dir=bin_dir)
