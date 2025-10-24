#!/bin/bash

set -e

MAKEFLAGS="-j$(nproc)"
export MAKEFLAGS

# poetry should be put into its own venv to avoid contaminating the dist build
# venv; otherwise nuitka can and will see additional imports leading to bloat
python3.13 -m venv /home/b/build-tools-venv
/home/b/build-tools-venv/bin/pip install -U pip setuptools wheel
/home/b/build-tools-venv/bin/pip install poetry
/home/b/build-tools-venv/bin/pip install maturin==1.9.6 cibuildwheel~=3.1.1 auditwheel==6.4.2
for tool in poetry maturin cibuildwheel auditwheel; do
    ln -s /home/b/build-tools-venv/bin/"$tool" /usr/local/bin/"$tool"
done

python3.13 -m venv /home/b/venv
/home/b/venv/bin/pip install -U pip setuptools wheel
chown -R "$BUILDER_UID:$BUILDER_GID" /home/b/venv

# remove wheel caches in the root user
rm -rf /root/.cache
