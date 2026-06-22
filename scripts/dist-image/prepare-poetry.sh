#!/bin/bash

set -e

MAKEFLAGS="-j$(nproc)"
export MAKEFLAGS

_PIP_INSTALL=( pip install )

# workaround too old rustc (1.81) when cryptography-49.0 has to be compiled,
# with an MSRV of 1.83
case "$(uname -m)" in
riscv64)
    wget https://static.rust-lang.org/rustup/dist/riscv64gc-unknown-linux-gnu/rustup-init
    chmod a+x rustup-init
    export RUSTUP_DIST_SERVER=https://mirrors.tuna.tsinghua.edu.cn/rustup/
    ./rustup-init -y  # because there is already a system Rust
    rustc -Vv
    _PIP_INSTALL+=(
        --prefer-binary
        --extra-index-url https://gitlab.com/api/v4/projects/riseproject%2Fpython%2Fwheel_builder/packages/pypi/simple
    )
    ;;
esac

_pip_install() {
    "${_PIP_INSTALL[@]}" "$@"
}

# poetry should be put into its own venv to avoid contaminating the dist build
# venv; otherwise nuitka can and will see additional imports leading to bloat
python3.14 -m venv /home/b/build-tools-venv
# shellcheck disable=SC1091
. /home/b/build-tools-venv/bin/activate
hash -r
_pip_install -U pip setuptools wheel
_pip_install poetry
_pip_install maturin==1.13.1 cibuildwheel~=3.4.1 auditwheel==6.6.0
deactivate
hash -r
for tool in poetry maturin cibuildwheel auditwheel; do
    ln -s /home/b/build-tools-venv/bin/"$tool" /usr/local/bin/"$tool"
done

python3.14 -m venv /home/b/venv
# shellcheck disable=SC1091
. /home/b/venv/bin/activate
hash -r
_pip_install -U pip setuptools wheel
deactivate
hash -r
chown -R "$BUILDER_UID:$BUILDER_GID" /home/b/venv

# remove wheel caches in the root user
rm -rf /root/.cache
