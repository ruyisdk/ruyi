#!/bin/bash

set -e

export POETRY_CACHE_DIR=/poetry-cache
export CCACHE_DIR=/ccache

cd /home/b
. ./venv/bin/activate

cd ruyi
poetry install

# patch Nuitka
pushd /home/b/venv/lib/python*/site-packages > /dev/null
patch -Np1 < /home/b/ruyi/scripts/patches/0001-Onefile-Respect-XDG_CACHE_HOME-when-rendering-CACHE_.patch
popd > /dev/null

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
    --onefile-tempdir-spec="{CACHE_DIR}/ruyi/progcache/${RUYI_DIST_SEMVER}"
    --include-package=pygments.formatters
    --include-package=pygments.lexers
    --include-package=pygments.styles
    ./ruyi/__main__.py
)

python -m nuitka "${nuitka_args[@]}"
