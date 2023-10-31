#!/bin/bash

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$REPO_ROOT"

arch="$1"
if [[ -z $arch ]]; then
    echo "usage: $0 <arch>" >&2
    echo >&2
    echo "see scripts/dist-image for available arch choices" >&2
    exit 1
fi

BUILD_DIR="$REPO_ROOT/tmp/build.${arch}"
POETRY_CACHE_DIR="$REPO_ROOT/tmp/poetry-cache.${arch}"
mkdir -p "$BUILD_DIR" "$POETRY_CACHE_DIR"

docker_args=(
    --rm
    --platform "linux/${arch}"
    -v "$REPO_ROOT":/home/b/ruyi:ro
    -v "$BUILD_DIR":/build
    -v "$POETRY_CACHE_DIR":/poetry-cache
    -t "ruyi-python-dist:20231031-${arch}"
    /home/b/ruyi/scripts/dist-inner.sh
)

exec docker run "${docker_args[@]}"
