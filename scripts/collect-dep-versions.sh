#!/usr/bin/env bash

: "${_INSIDE_DOCKER:=false}"

ARCH_APT_PKGS=(
    libc6
    python3
    python3-pygit2
    python3-yaml
)

ARCH_DNF_PKGS=(
    glibc
    python3
    python3-pygit2
    python3-pyyaml
)

NOARCH_PKGS=(
    python3-argcomplete
    python3-arpy
    python3-babel
    python3-certifi
    python3-fastjsonschema
    python3-jinja2
    python3-requests
    python3-rich
    python3-semver
    python3-tomlkit
    python3-typing-extensions
)

main() {
    local image_tag="$1"

    if "$_INSIDE_DOCKER"; then
        # shellcheck disable=SC1091
        [[ -f /etc/os-release ]] && source /etc/os-release
        : "${PRETTY_NAME:=$image_tag}"

        if command -v apt-get > /dev/null; then
            probe_apt "$PRETTY_NAME"
            exit $?
        fi
        if command -v dnf > /dev/null; then
            probe_dnf "$PRETTY_NAME"
            exit $?
        fi
        echo "error: unknown package manager for container image $image_tag" >&2
        exit 1
    fi

    if [[ -z $image_tag ]]; then
        echo "usage: $0 <image-tag-to-probe>" >&2
        exit 2
    fi

    local args=(
        --rm
        -e _INSIDE_DOCKER=true
        -v "${BASH_SOURCE[0]}:/inner.sh"
        "$image_tag"
        "/inner.sh"
        "$image_tag"
    )

    exec docker run "${args[@]}"
}

_strip_pkgver_suffix() {
    local v="$1"
    v="${v%-*}"
    v="${v%+*}"
    echo "$v"
}

_query_apt_pkgver() {
    local pkg="$1"
    local result
    result="$(apt-cache show "$pkg" 2> /dev/null | grep -E '^Version: ' | head -n1 | sed -E 's/^Version: //')"
    echo "${result:-:x:}"
}

probe_apt() {
    local pretty_name="$1"
    local arch_data_row="| $pretty_name |"
    local noarch_data_row="| $pretty_name |"
    local pkgver

    apt-get update

    for pkg in "${ARCH_APT_PKGS[@]}"; do
        printf "querying apt for %s..." "$pkg"
        pkgver="$(_query_apt_pkgver "$pkg")"
        echo " $pkgver"
        arch_data_row="$arch_data_row $(_strip_pkgver_suffix "$pkgver") |"
    done

    for pkg in "${NOARCH_PKGS[@]}"; do
        printf "querying apt for %s..." "$pkg"
        pkgver="$(_query_apt_pkgver "$pkg")"
        echo " $pkgver"
        noarch_data_row="$noarch_data_row $(_strip_pkgver_suffix "$pkgver") |"
    done

    echo
    echo "$arch_data_row"
    echo
    echo "$noarch_data_row"
    echo
}

_query_dnf_pkgver() {
    local pkg="$1"
    local result
    result="$(dnf info "$pkg" 2> /dev/null | grep -E '^Version +: ' | head -n1 | sed -E 's/^Version +: //')"
    echo "${result:-:x:}"
}

probe_dnf() {
    local pretty_name="$1"
    local arch_data_row="| $pretty_name |"
    local noarch_data_row="| $pretty_name |"
    local pkgver

    dnf check-update

    for pkg in "${ARCH_DNF_PKGS[@]}"; do
        printf "querying dnf for %s..." "$pkg"
        pkgver="$(_query_dnf_pkgver "$pkg")"
        echo " $pkgver"
        arch_data_row="$arch_data_row $(_strip_pkgver_suffix "$pkgver") |"
    done

    for pkg in "${NOARCH_PKGS[@]}"; do
        printf "querying dnf for %s..." "$pkg"
        pkgver="$(_query_dnf_pkgver "$pkg")"
        echo " $pkgver"
        noarch_data_row="$noarch_data_row $(_strip_pkgver_suffix "$pkgver") |"
    done

    echo
    echo "$arch_data_row"
    echo
    echo "$noarch_data_row"
    echo
}

main "$@"
