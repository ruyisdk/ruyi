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

# workaround patchelf 0.18.0 being broken for Nuitka by downgrading to the latest
# maintenance release as of June 2026
#
# for now this just applies to riscv64's deepin 25
case "$(uname -m):$(patchelf --version | cut -f2 -d' ')" in
riscv64:0.18.0*)
    mkdir tmp.patchelf
    pushd tmp.patchelf

    echo "011617086323d4f1f959b83ca508f1f89edaabd5f5c3be49d2574cad044f0daa  patchelf-0.15.5-riscv64.tar.gz" > patchelf.sha256sum
    wget https://github.com/NixOS/patchelf/releases/download/0.15.5/patchelf-0.15.5-riscv64.tar.gz
    sha256sum -c patchelf.sha256sum
    tar xf ./patchelf-0.15.5-riscv64.tar.gz
    mv bin/patchelf /usr/local/bin/patchelf
    hash -r
    patchelf --version

    popd
    rm -rf tmp.patchelf
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
