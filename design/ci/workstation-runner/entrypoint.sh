#!/usr/bin/env bash
# Register once (token from Settings > Actions > Runners > New runner), then run.
set -euo pipefail
cd /home/runner/actions-runner
if [[ ! -f .runner ]]; then
    : "${OX_RUNNER_TOKEN:?set OX_RUNNER_TOKEN to a registration token for the first start}"
    ./config.sh --unattended --replace \
        --url "https://github.com/${OX_RUNNER_REPO:-Earnest-Williams/Ox-of-Hephaestus}" \
        --token "${OX_RUNNER_TOKEN}" \
        --name "${OX_RUNNER_NAME:-ox-workstation}" \
        --labels ox-workstation \
        --work /home/runner/_work
fi
exec ./run.sh
