#!/bin/bash

set -e

export MAKEFLAGS="-j$(nproc)"

# poetry should be put into its own venv to avoid contaminating the dist build
# venv; otherwise nuitka can and will see additional imports leading to bloat
python3.12 -m venv /home/b/poetry-venv
/home/b/poetry-venv/bin/pip install -U pip setuptools wheel
/home/b/poetry-venv/bin/pip install poetry
/home/b/poetry-venv/bin/pip install maturin==1.6.0 cibuildwheel==2.19.1 auditwheel==6.0.0
ln -s /home/b/poetry-venv/bin/poetry /usr/local/bin/poetry

python3.12 -m venv /home/b/venv
chown -R "$BUILDER_UID:$BUILDER_GID" /home/b/venv

# remove wheel caches in the root user
rm -rf /root/.cache
