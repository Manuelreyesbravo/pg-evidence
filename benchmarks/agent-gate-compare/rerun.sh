#!/usr/bin/env bash
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
#
# Rerun the cited MCP comparison on a clean GitHub runner, from YOUR fork of agent-gate-demo,
# wait for it, download its artifact and turn it into a submitted result.
#
#   benchmarks/agent-gate-compare/rerun.sh you/agent-gate-demo
#
# Needs gh, logged in, and a fork with Actions enabled. The run takes about an hour on CPU.
set -euo pipefail
FORK=${1:?usage: rerun.sh <owner>/agent-gate-demo}
CONFIG=${CONFIG:-cited}
BY=${BY:-$(git config user.name || echo unknown)}

gh workflow run compare.yml -R "$FORK" -f config="$CONFIG" -f repeat="${REPEAT:-1}"
sleep 10
RUN_ID=$(gh run list -R "$FORK" --workflow compare.yml --limit 1 --json databaseId -q '.[0].databaseId')
echo "run: https://github.com/$FORK/actions/runs/$RUN_ID"
gh run watch -R "$FORK" "$RUN_ID" --exit-status
DIR=$(mktemp -d)
gh run download -R "$FORK" "$RUN_ID" -n "compare-results-$CONFIG" -D "$DIR"
python3 tools/ingest.py agent-gate-compare "$DIR" --by "$BY" --date "$(date -u +%F)"
python3 tools/validate.py
