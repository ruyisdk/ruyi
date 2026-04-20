# syntax=docker/dockerfile:1
FROM ubuntu:24.04

ARG TARGETARCH
ARG BUILDER_UID=1000
ARG BUILDER_GID=1000

SHELL ["/bin/bash", "-c"]

RUN <<DOCKEREOF
_getent_result="$(getent passwd "$BUILDER_UID")"

if [[ -n $_getent_result ]]; then
    ln -s "/home/${_getent_result%%:*}" /home/b
else
    groupadd -g "$BUILDER_GID" b
    useradd -d /home/b -m -g "$BUILDER_GID" -u "$BUILDER_UID" -s /bin/bash b
fi
DOCKEREOF

RUN <<DOCKEREOF
export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# HTTPS needs ca-certificates to work
# Ubuntu 24.04+ uses deb822 files under /etc/apt/sources.list.d/
sed -E -i 's@http://(archive|ports)\.ubuntu\.com/@http://mirrors.huaweicloud.com/@g' /etc/apt/sources.list.d/*

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
    python3.12-dev

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

    # for docker/setup-qemu-action
    docker.io

    # for ruyi-litester
    jq
    llvm-20-tools
    pipx
    schroot
    # wget
    yq
)

apt-get update
apt-get upgrade -qqy
apt-get install -qqy "${package_list[@]}"

ln -s /usr/bin/FileCheck-20 /usr/local/bin/FileCheck

apt-get clean
rm -rf /var/lib/apt/lists/*
DOCKEREOF

# Python 3.14.4 + Nuitka 2.8.10 produces ruyi binaries that segfault during
# apply_config
COPY --link ./build-python.sh /tmp/
RUN /tmp/build-python.sh

COPY --link ./prepare-poetry.sh /tmp/prepare-poetry.sh
RUN /tmp/prepare-poetry.sh

USER $BUILDER_UID:$BUILDER_GID
WORKDIR /home/b
