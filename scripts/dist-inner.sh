#!/bin/bash

set -e

export POETRY_CACHE_DIR=/poetry-cache

cd /home/b
. ./venv/bin/activate

cd ruyi
poetry install

nuitka_args=(
    --standalone
    --onefile
    --output-filename=ruyi
    --output-dir=/build
    ./ruyi/__main__.py
)

python -m nuitka "${nuitka_args[@]}"
