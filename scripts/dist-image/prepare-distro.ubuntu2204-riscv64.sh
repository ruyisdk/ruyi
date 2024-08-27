#!/bin/bash

set -e

groupadd -g "$BUILDER_GID" b
useradd -d /home/b -m -g "$BUILDER_GID" -u "$BUILDER_UID" -s /bin/bash b

export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# HTTPS needs ca-certificates to work
sed -i 's@http://ports\.ubuntu\.com/@http://mirrors.tuna.tsinghua.edu.cn/@g' /etc/apt/sources.list

# Non-interactive configuration of tzdata
debconf-set-selections <<EOF
tzdata tzdata/Areas select Etc
tzdata tzdata/Zones/Etc select UTC
EOF

package_list=(
    build-essential

    # for Nuitka
    zlib1g-dev  # likely for one-file builds
    patchelf    # for one-file builds
    ccache      # for rebuilds
    git         # for GHA checkout action

    # for pulling in build deps only
    python3.11-dev

    # Python library deps
    # cffi
    libffi-dev
    # cryptography
    rustc
    cargo
    # Rust openssl-sys
    libssl-dev
    pkgconf
    # pygit2 build
    cmake
    wget
)

apt-get update
apt-get upgrade -qqy
apt-get install -qqy "${package_list[@]}"

apt-get clean

# Nuitka now requires final versions of Python, but unfortunately the python3.11
# in the jammy repo is 3.11.0rc1, and there's no python3.12 in repo, so we have
# to build our own Python for now.
#
# See: https://github.com/Nuitka/Nuitka/commit/54f2a2222abedf92d45b8f397233cfb3bef340c5

PYTHON_V=3.12.5
pushd /tmp
wget https://www.python.org/ftp/python/${PYTHON_V}/Python-${PYTHON_V}.tar.xz
mkdir py-src py-build
tar -xf "Python-${PYTHON_V}.tar.xz" --strip-components=1 -C py-src

pushd py-build
../py-src/configure --prefix=/usr/local
make -j
make install
popd

rm -rf py-src py-build Python-*.tar.xz
popd
