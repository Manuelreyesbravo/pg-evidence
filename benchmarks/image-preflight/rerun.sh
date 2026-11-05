#!/usr/bin/env bash
# Copyright 2026 Manuel Reyes Bravo
# SPDX-License-Identifier: Apache-2.0
#
# Rerun Red Hat's preflight on the cited image, by digest, with no registry credential.
#
#   benchmarks/image-preflight/rerun.sh
#
# Needs preflight 1.22.0 (https://github.com/redhat-openshift-ecosystem/openshift-preflight/releases).
set -euo pipefail
IMAGE=${IMAGE:-ghcr.io/latamflows/ygg-pg@sha256:9962ad3fac92af86ff813822aa33c8c9d3f37d49a1eaf4eaa34d43cb91e5f5c3}
PREFLIGHT_COMMIT=${PREFLIGHT_COMMIT:-1195775769d05581060691fdcbd584b8a36e8ddd}
BY=${BY:-$(git config user.name || echo unknown)}
DIR=$(mktemp -d)
EMPTY=$(mktemp -d)
# An empty auth context: the pull must work anonymously, as it does for anyone.
DOCKER_CONFIG=$EMPTY REGISTRY_AUTH_FILE=$EMPTY/auth.json \
    preflight check container "$IMAGE" --artifacts "$DIR/artifacts" > "$DIR/stdout.json"
python3 tools/ingest.py image-preflight "$DIR" --by "$BY" --date "$(date -u +%F)" \
    --image-digest "${IMAGE#*@}" --preflight-commit "$PREFLIGHT_COMMIT"
python3 tools/validate.py
