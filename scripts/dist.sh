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
        # shellcheck disable=SC1091
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

    : "${VIRTUAL_ENV:?you must build in a Python virtual environment}"

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

    # build dep(s) with extension(s) if no prebuilt artifact is available on PyPI
    case "$arch" in
    amd64|arm64|ppc64el) ;;  # current as of 1.17.0
    *) ./scripts/build-pygit2.py ;;
    esac

    green "installing deps" group
    poetry install --with=dist --without=dev
    endgroup

    if [[ -d ${REPO_ROOT}/scripts/patches/nuitka ]]; then
        green "patching Nuitka" group
        pushd "$VIRTUAL_ENV"/lib/python*/site-packages > /dev/null
        for patch_file in "$REPO_ROOT"/scripts/patches/nuitka/*.patch; do
            echo "    * $(basename "$patch_file")"
            patch -Np1 < "$patch_file"
        done
        popd > /dev/null
        endgroup
    fi

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

    local host_arch="$1"
    local build_arch
    local build_arch_is_officially_supported=false

    build_arch="$(convert_uname_arch_to_ruyi "$(uname -m)")"
    if is_docker_dist_build_supported "$build_arch"; then
        build_arch_is_officially_supported=true
    fi

    if [[ -z $host_arch ]]; then
        host_arch="$build_arch"
        echo "usage: $0 [arch]" >&2
        echo "info: defaulting to build machine arch $build_arch" >&2
    fi

    if is_docker_dist_build_supported "$host_arch"; then
        do_docker_build "$host_arch"
    else
        echo "warning: Docker-based dist builds for architecture $host_arch is not supported" >&2
        if [[ -n "$RUYI_DIST_FORCE_IMAGE_TAG" ]]; then
            # but this is explicitly requested so...
            do_docker_build "$host_arch"
        else
            # Because of the way Nuitka works, cross builds cannot be supported.
            #
            # But without knowledge of the Debian name for the user's arch, we
            # cannot know whether the user is actually doing native builds on
            # their arch, with $build_arch expected to differ from `uname -m`
            # output.
            #
            # On the other hand, if the build arch is supported, when
            # $host_arch differs from $build_arch we can indeed be sure that
            # the build will fail.
            if [[ $build_arch != "$host_arch" ]]; then
                if "$build_arch_is_officially_supported"; then
                    echo "error: cross building is not possible with Nuitka" >&2
                    echo "info: to our knowledge, $host_arch is not the same as $build_arch" >&2
                    echo "info: please retry with $host_arch hardware / emulation / sysroot instead" >&2
                    exit 1
                fi

                echo "warning: the requested arch $host_arch differs from the build machine arch $build_arch, but the build is not Docker-based" >&2
                echo "warning: cross builds are not supported and will fail" >&2
            fi

            echo "warning: your build may not be reproducible" >&2
            do_inner "$@"
        fi
    fi
}

main "$@"
