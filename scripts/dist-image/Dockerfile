# syntax=docker/dockerfile:1
FROM ubuntu:22.04

ARG TARGETARCH
ARG BUILDER_UID=1000
ARG BUILDER_GID=1000

SHELL ["/bin/bash", "-c"]

RUN <<DOCKEREOF
groupadd -g "$BUILDER_GID" b
useradd -d /home/b -m -g "$BUILDER_GID" -u "$BUILDER_UID" -s /bin/bash b
DOCKEREOF

RUN <<DOCKEREOF
export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# HTTPS needs ca-certificates to work
sed -E -i 's@http://(archive|ports)\.ubuntu\.com/@http://mirrors.tuna.tsinghua.edu.cn/@g' /etc/apt/sources.list

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
rm -rf /var/lib/apt/lists/*
DOCKEREOF

COPY ./build-python.sh /tmp/
RUN /tmp/build-python.sh

COPY ./prepare-poetry.sh /tmp/prepare-poetry.sh
RUN /tmp/prepare-poetry.sh

USER $BUILDER_UID:$BUILDER_GID
WORKDIR /home/b
