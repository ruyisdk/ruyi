#!/bin/bash

set -e

MAKEFLAGS="-j$(nproc)"
export MAKEFLAGS

# in order to accommodate both our traditional dist builds and the GHA-driven
# containerized builds, move the venv dirs to /opt.

cd /opt

# poetry should be put into its own venv to avoid contaminating the dist build
# venv; otherwise nuitka can and will see additional imports leading to bloat
python3.12 -m venv build-tools-venv
build-tools-venv/bin/pip install -U pip setuptools wheel
build-tools-venv/bin/pip install poetry
build-tools-venv/bin/pip install maturin==1.8.3 cibuildwheel==2.23.2 auditwheel==6.3.0
for tool in poetry maturin cibuildwheel auditwheel; do
    ln -s build-tools-venv/bin/"$tool" /usr/local/bin/"$tool"
done

python3.12 -m venv venv
venv/bin/pip install -U pip setuptools wheel

if [[ -n $BUILDER_UID ]] && [[ -n $BUILDER_GID ]]; then
    echo Resetting build venv owner to "$BUILDER_UID:$BUILDER_GID"
    chown -R "$BUILDER_UID:$BUILDER_GID" venv
fi

# remove wheel caches in the root user
rm -rf /root/.cache
