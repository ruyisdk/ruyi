#!/bin/bash

set -e

export MAKEFLAGS="-j$(nproc)"

python3.11 -m venv /home/b/venv
/home/b/venv/bin/pip install -U pip setuptools wheel
/home/b/venv/bin/pip install poetry
chown -R "$BUILDER_UID:$BUILDER_GID" /home/b/venv

# remove wheel caches in the root user
rm -rf /root/.cache
