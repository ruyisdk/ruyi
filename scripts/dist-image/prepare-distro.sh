#!/usr/bin/env bash

# shellcheck disable=SC1091
. /etc/os-release
: "${ID:=}"
: "${VERSION_ID:=}"

case "$ID" in
debian|deepin|ubuntu)
    _PM=apt
    ;;
fedora|openEuler)
    _PM=dnf
    ;;
*)
    echo "error: unrecognized distro ID '$ID'" >&2
    exit 2
    ;;
esac

case "$ID:$VERSION_ID" in
debian:12)
    _SYS_LLVM_VER=16
    _SYS_PYTHON_VER=3.11
    ;;
deepin:25)
    _SYS_LLVM_VER=19
    _SYS_PYTHON_VER=3.12
    ;;
openEuler:*)
    # no special handling needed for Python devel libs
    _SYS_LLVM_VER=20
    ;;
ubuntu:24.04)
    _SYS_LLVM_VER=20
    _SYS_PYTHON_VER=3.12
    ;;
*)
    echo "error: unrecognized distro version '$ID:$VERSION_ID'" >&2
    exit 2
    ;;
esac

main() {
    add_builder_user
    case "$_PM" in
    apt)
        prepare_apt_distro
        ;;
    dnf)
        prepare_dnf_distro
        ;;
    *)
        exit 2
        ;;
    esac
}

add_builder_user() {
    _getent_result="$(getent passwd "$BUILDER_UID")"

    if [[ -n $_getent_result ]]; then
        ln -s "$(cut -f6 -d: <<<"$_getent_result")" /home/b
    else
        groupadd -g "$BUILDER_GID" b
        useradd -d /home/b -m -g "$BUILDER_GID" -u "$BUILDER_UID" -s /bin/bash b
    fi
}

prepare_apt_distro() {
    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true

    # HTTPS needs ca-certificates to work
    # Debian 12+ and Ubuntu 24.04+ both use deb822 files under /etc/apt/sources.list.d/
    case "$ID" in
    debian)
        sed -E -i 's@http://deb\.debian\.org/@http://mirrors.huaweicloud.com/@g' /etc/apt/sources.list.d/*
        ;;
    ubuntu)
        sed -E -i 's@http://(archive|ports)\.ubuntu\.com/@http://mirrors.huaweicloud.com/@g' /etc/apt/sources.list.d/*
        ;;
    deepin)
        sed -E -i 's@https://community-packages\.deepin\.com@https://mirrors.huaweicloud.com/deepin@' /etc/apt/sources.list
        ;;
    esac

    # Non-interactive configuration of tzdata
    debconf-set-selections <<EOF
tzdata tzdata/Areas select Etc
tzdata tzdata/Zones/Etc select UTC
EOF

    local package_list=(
        build-essential

        # for Nuitka
        zlib1g-dev  # likely for one-file builds
        patchelf    # for one-file builds
        ccache      # for rebuilds
        git         # for GHA checkout action

        # for pulling in build deps only
        "python${_SYS_PYTHON_VER}-dev"

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
        "llvm-${_SYS_LLVM_VER}-tools"
        pipx
        schroot
        # wget  # already included
        yq
    )

    apt-get update
    apt-get upgrade -qqy
    apt-get install -qqy "${package_list[@]}"

    ln -s "/usr/bin/FileCheck-$_SYS_LLVM_VER" /usr/local/bin/FileCheck

    apt-get clean
    rm -rf /var/lib/apt/lists/*
}

prepare_dnf_distro() {
    # timezone is already UTC, requiring no explicit intervention unlike debconf
    #
    # this base image being openEuler, mirrors are already CN-based

    local package_list=(
        gcc
        gcc-c++
        make

        # for Nuitka
        zlib-devel  # likely for one-file builds
        patchelf    # for one-file builds
        ccache      # for rebuilds
        git         # for GHA checkout action

        # for pulling in build deps only
        python3-devel

        # Python library deps
        # cffi
        libffi-devel
        # cryptography
        rust
        cargo
        # Rust openssl-sys
        openssl-devel
        pkgconf-pkg-config
        # pygit2 build
        cmake
        wget

        # for docker/setup-qemu-action
        docker

        # for ruyi-litester
        jq
        "llvm-toolset-${_SYS_LLVM_VER}"
        pipx
        # schroot  # unavailable
        # wget  # already included
        # yq  # unavailable
    )

    dnf -y upgrade --refresh
    dnf -y install "${package_list[@]}"

    ln -s "/usr/bin/FileCheck-$_SYS_LLVM_VER" /usr/local/bin/FileCheck

    # openEuler does not have yq in archive
    wget -O /usr/local/bin/yq "https://github.com/mikefarah/yq/releases/download/v4.53.2/yq_linux_$TARGETARCH"
    chmod a+x /usr/local/bin/yq

    dnf clean all
    rm -rf /var/cache/dnf
}

main "$@"
