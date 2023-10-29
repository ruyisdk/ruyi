#!/bin/bash

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$REPO_ROOT"

BUILD_DIR="$REPO_ROOT/tmp/build"
POETRY_CACHE_DIR="$REPO_ROOT/tmp/poetry-cache"
mkdir -p "$BUILD_DIR" "$POETRY_CACHE_DIR"

docker_args=(
    --rm
    -v "$REPO_ROOT":/home/b/ruyi:ro
    -v "$BUILD_DIR":/build
    -v "$POETRY_CACHE_DIR":/poetry-cache
    -t ruyi-python-dist:ubuntu2204-20231029
    /home/b/ruyi/scripts/dist-inner.sh
)

exec docker run "${docker_args[@]}"
