#!/usr/bin/env bash
# Mutation gate: restores the pinned local tools, then runs Stryker.NET with stryker-config.json.
# Extra arguments pass through, for example: scripts/run-mutation-tests.sh --since:origin/main
# Needs a running container engine (the integration tests start PostgreSQL). Takes minutes, so it is a separate job.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v docker >/dev/null && docker info >/dev/null 2>&1 || { echo 'container engine not running (needed by Testcontainers)' >&2; exit 1; }
dotnet tool restore
dotnet dotnet-stryker --config-file stryker-config.json "$@"
