#!/bin/bash
# this file is meant to be sourced

_COMMON_DIST_IMAGE_TAG="ghcr.io/ruyisdk/ruyi-python-dist:20250107"

# Map of `uname -m` outputs to Debian arch name convention which Ruyi adopts
#
# This list is incomplete: it currently only contains architectures for which
# Docker-based dist builds are supported, and that are officially supported
# by the RuyiSDK project. This means if you want to build for an architecture
# that is not officially supported, and if `uname -m` output differs from
# the Debian name for it, you will have to specify the correct arch name on
# the command line.
declare -A _UNAME_ARCH_MAP=(
    ["aarch64"]="arm64"
    ["i686"]="i386"
    ["x86_64"]="amd64"
)

convert_uname_arch_to_ruyi() {
    echo "${_UNAME_ARCH_MAP["$1"]:-"$1"}"
}

declare -A _RUYI_DIST_IMAGE_TAGS=(
    ["amd64"]="$_COMMON_DIST_IMAGE_TAG"
    ["arm64"]="$_COMMON_DIST_IMAGE_TAG"
    ["riscv64"]="$_COMMON_DIST_IMAGE_TAG"
)

is_docker_dist_build_supported() {
    local arch="$1"
    [[ -n "${_RUYI_DIST_IMAGE_TAGS["$arch"]}" ]]
}

ensure_docker_dist_build_supported() {
    local arch="$1"
    local loglevel=error

    if [[ -n "$RUYI_DIST_FORCE_IMAGE_TAG" ]]; then
        loglevel=warning
    fi

    if ! is_docker_dist_build_supported "$arch"; then
        echo "$loglevel: unsupported arch $arch for Docker-based dist builds" >&2
        echo "info: supported arches:" "${!_RUYI_DIST_IMAGE_TAGS[@]}" >&2
        if [[ $loglevel == error ]]; then
            echo "info: you can set RUYI_DIST_FORCE_IMAGE_TAG (and maybe RUYI_DIST_GOARCH) if you insist" >&2
            exit 1
        fi
    fi
}

image_tag_base() {
    local arch="$1"

    if [[ -n "$RUYI_DIST_FORCE_IMAGE_TAG" ]]; then
        echo "warning: forcing use of dist image $RUYI_DIST_FORCE_IMAGE_TAG" >&2
        echo "$RUYI_DIST_FORCE_IMAGE_TAG"
        return 0
    fi

    ensure_docker_dist_build_supported "$arch"
    echo "${_RUYI_DIST_IMAGE_TAGS["$arch"]}"
}
