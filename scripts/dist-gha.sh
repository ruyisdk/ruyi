#!/bin/bash

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# this has to mirror the setup in the GHA workflow and scripts/dist.sh
export CCACHE_DIR=/github/workspace/build-cache/ccache
export POETRY_CACHE_DIR=/github/workspace/build-cache/poetry-cache
export RUYI_DIST_BUILD_DIR=/github/workspace/build
export RUYI_DIST_CACHE_DIR=/github/workspace/build-cache/ruyi-dist-cache
export RUYI_DIST_INNER_CONTAINERIZED=x
export RUYI_DIST_INNER=x
"$MY_DIR"/dist.sh "$@"
ret=$?

# fix the cache directory's ownership if necessary
cache_uid="$(stat -c '%u' /github/workspace/build-cache)"
workspace_uid="$(stat -c '%u' /github/workspace)"
if [[ $cache_uid -ne $workspace_uid ]]; then
    echo "fixing ownership of build cache directory"
    chown -v --reference=/github/workspace /github/workspace/build-cache
fi

exit $ret
