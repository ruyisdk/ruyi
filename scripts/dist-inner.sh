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

./scripts/dist-inner.py
