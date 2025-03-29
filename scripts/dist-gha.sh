#!/bin/bash

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# this has to mirror the setup in the GHA workflow and scripts/dist.sh
export CCACHE_DIR=/github/workspace/build-cache/ccache
export POETRY_CACHE_DIR=/github/workspace/build-cache/poetry-cache
export RUYI_DIST_BUILD_DIR=/github/workspace/build
export RUYI_DIST_CACHE_DIR=/github/workspace/build-cache/ruyi-dist-cache
export RUYI_DIST_INNER_CONTAINERIZED=x
export RUYI_DIST_INNER=x
exec "$MY_DIR"/dist.sh "$@"
