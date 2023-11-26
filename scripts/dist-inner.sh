#!/bin/bash

set -e

export POETRY_CACHE_DIR=/poetry-cache
export CCACHE_DIR=/ccache

cd /home/b
. ./venv/bin/activate

cd ruyi
poetry install

eval "$(./scripts/_dist_version_helper.py)"

echo "Project SemVer       : $RUYI_DIST_SEMVER"
echo "Nuitka version to use: $RUYI_DIST_NUITKA_VER"

nuitka_args=(
    --standalone
    --onefile
    --output-filename=ruyi
    --output-dir=/build
    --no-deployment-flag=self-execution
    --product-version="$RUYI_DIST_NUITKA_VER"
    --onefile-tempdir-spec="%CACHE_DIR%/ruyi/progcache/${RUYI_DIST_SEMVER}"
    ./ruyi/__main__.py
)

python -m nuitka "${nuitka_args[@]}"
