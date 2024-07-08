#!/bin/bash

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
cd "$REPO_ROOT"

source "${REPO_ROOT}/scripts/_image_tag_base.sh"

green() {
    if [[ $2 == group ]]; then
        if [[ -n $GITHUB_ACTIONS ]]; then
            echo "::group::$1"
            return
        fi
    fi
    printf "\x1b[1;32m%s\x1b[m\n" "$1"
}

endgroup() {
    if [[ -n $GITHUB_ACTIONS ]]; then
        echo "::endgroup::"
    fi
}

do_inner() {
    local arch="$1"

    if [[ -n $RUYI_DIST_INNER_CONTAINERIZED ]]; then
        cd /home/b
        . ./venv/bin/activate
    else
        # we're running in the host environment
        # give defaults for the directories
        local tmp_prefix="$REPO_ROOT/tmp"
        : "${CCACHE_DIR:=$tmp_prefix/ccache.$arch}"
        : "${POETRY_CACHE_DIR:=$tmp_prefix/poetry-cache.$arch}"
        : "${RUYI_DIST_BUILD_DIR:=$tmp_prefix/build.$arch}"
        : "${RUYI_DIST_CACHE_DIR:=$tmp_prefix/ruyi-dist-cache.$arch}"
        export CCACHE_DIR POETRY_CACHE_DIR RUYI_DIST_BUILD_DIR RUYI_DIST_CACHE_DIR
        mkdir -p "$RUYI_DIST_BUILD_DIR" "$POETRY_CACHE_DIR" "$CCACHE_DIR" "$RUYI_DIST_CACHE_DIR"
    fi

    : "${MAKEFLAGS:=-j$(nproc)}"
    export MAKEFLAGS

    if [[ -n $CI ]]; then
        green "current user info" group
        id
        endgroup
        green "home directory contents" group
        ls -alF .
        endgroup
        green "repo contents" group
        ls -alF "$REPO_ROOT"
        endgroup
        green "ruyi-dist-cache contents" group
        ls -alF "$RUYI_DIST_CACHE_DIR"
        endgroup

        if [[ ! -O $REPO_ROOT ]]; then
            green "adding the repo to the list of Git safe directories"
            git config --global --add safe.directory "$REPO_ROOT"
        fi
    fi

    [[ -n $RUYI_DIST_INNER_CONTAINERIZED ]] && cd "$REPO_ROOT"

    # build pygit2 and/or xingque if no prebuilt artifact is available on PyPI
    case "$arch" in
    amd64|arm64|ppc64el) ;;  # current as of 1.15.1
    *) ./scripts/build-pygit2.py ;;
    esac

    case "$arch" in
    amd64|arm64|armhf|i386|ppc64el|s390x) ;;  # current as of 0.2.0
    *) ./scripts/build-xingque.py ;;
    esac

    green "installing deps" group
    poetry install --with=dist --without=dev
    endgroup

    exec ./scripts/dist-inner.py
}

do_docker_build() {
    local arch="$1"
    local goarch="${RUYI_DIST_GOARCH:-$arch}"

    local CCACHE_DIR="$REPO_ROOT/tmp/ccache.${arch}"
    local POETRY_CACHE_DIR="$REPO_ROOT/tmp/poetry-cache.${arch}"
    local RUYI_DIST_BUILD_DIR="$REPO_ROOT/tmp/build.${arch}"
    local RUYI_DIST_CACHE_DIR="$REPO_ROOT/tmp/ruyi-dist-cache.${arch}"
    mkdir -p "$CCACHE_DIR" "$POETRY_CACHE_DIR" "$RUYI_DIST_BUILD_DIR" "$RUYI_DIST_CACHE_DIR"

    docker_args=(
        --rm
        -i  # required to be able to interrupt the build with ^C
        --platform "linux/${goarch}"
        -v "$REPO_ROOT":/home/b/ruyi
        -v "$CCACHE_DIR":/ccache
        -v "$POETRY_CACHE_DIR":/poetry-cache
        -v "$RUYI_DIST_BUILD_DIR":/build
        -v "$RUYI_DIST_CACHE_DIR":/ruyi-dist-cache
        -e RUYI_DIST_INNER=x
        -e RUYI_DIST_INNER_CONTAINERIZED=x
        -e CCACHE_DIR=/ccache
        -e POETRY_CACHE_DIR=/poetry-cache
        -e RUYI_DIST_BUILD_DIR=/build
        -e RUYI_DIST_CACHE_DIR=/ruyi-dist-cache
    )

    # only allocate pty if currently running interactively
    # check if stdout is a tty
    if [[ -t 1 ]]; then
        docker_args+=( -t )
    fi

    docker_args+=(
        "$(image_tag_base "$arch")"
        /home/b/ruyi/scripts/dist.sh "$arch"
    )

    exec docker run "${docker_args[@]}"
}

main() {
    if [[ -n $RUYI_DIST_INNER ]]; then
        do_inner "$@"
    fi

    local arch="$1"
    if [[ -z $arch ]]; then
        arch="$(convert_uname_arch_to_ruyi "$(uname -m)")"
        echo "usage: $0 [arch]" >&2
        echo "info: defaulting to host arch $arch" >&2
    fi

    if is_docker_dist_build_supported "$arch"; then
        do_docker_build "$arch"
    else
        echo "warning: Docker-based dist builds for architecture $arch is not supported" >&2
        if [[ -n "$RUYI_DIST_FORCE_IMAGE_TAG" ]]; then
            # but this is explicitly requested so...
            do_docker_build "$arch"
        else
            echo "warning: your build may not be reproducible" >&2
            do_inner "$@"
        fi
    fi
}

main "$@"
