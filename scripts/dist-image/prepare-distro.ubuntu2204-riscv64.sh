#!/bin/bash

set -e

groupadd -g "$BUILDER_GID" b
useradd -d /home/b -m -g "$BUILDER_GID" -u "$BUILDER_UID" -s /bin/bash b

export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# HTTPS needs ca-certificates to work
# sed -i 's@http://archive\.ubuntu\.com/@http://mirrors.huaweicloud.com/@g' /etc/apt/sources.list

# Non-interactive configuration of tzdata
debconf-set-selections <<EOF
tzdata tzdata/Areas select Etc
tzdata tzdata/Zones/Etc select UTC
EOF

package_list=(
    build-essential

    # for Nuitka
    python3.11-dev
    zlib1g-dev  # likely for one-file builds
    patchelf    # for one-file builds
    ccache      # for rebuilds
    git         # for GHA checkout action

    # for the Python build env
    python3.11-venv

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
# apt-get upgrade -qqy  # assume the base snapshots are reasonably up-to-date
apt-get install -y "${package_list[@]}"

apt-get clean
