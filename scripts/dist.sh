#!/bin/bash

set -e

green() {
    printf "\x1b[1;32m%s\x1b[m\n" "$1"
}

do_inner() {
    export POETRY_CACHE_DIR=/poetry-cache
    export CCACHE_DIR=/ccache
    export MAKEFLAGS="-j$(nproc)"

    cd /home/b
    . ./venv/bin/activate

    if [[ -n $CI ]]; then
        green "current user info"
        id
        green "home directory contents"
        ls -alF .
        green "repo contents"
        ls -alF ./ruyi
        green "ruyi-dist-cache contents"
        ls -alF /ruyi-dist-cache
    fi

    cd ruyi
    case "$(uname -m)" in
    riscv64)
        ./scripts/build-pygit2.py
        ;;
    esac

    poetry install

    # patch Nuitka
    pushd /home/b/venv/lib/python*/site-packages > /dev/null
    patch -Np1 < /home/b/ruyi/scripts/patches/0001-Onefile-Respect-XDG_CACHE_HOME-when-rendering-CACHE_.patch
    popd > /dev/null

    exec ./scripts/dist-inner.py
}

if [[ -n $RUYI_DIST_INNER ]]; then
    do_inner
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"

cd "$REPO_ROOT"

arch="$1"
if [[ -z $arch ]]; then
    echo "usage: $0 <arch>" >&2
    echo >&2
    echo "see scripts/dist-image for available arch choices" >&2
    exit 1
fi

source "${REPO_ROOT}/scripts/_image_tag_base.sh"

BUILD_DIR="$REPO_ROOT/tmp/build.${arch}"
POETRY_CACHE_DIR="$REPO_ROOT/tmp/poetry-cache.${arch}"
CCACHE_DIR="$REPO_ROOT/tmp/ccache.${arch}"
RUYI_DIST_CACHE_DIR="$REPO_ROOT/tmp/ruyi-dist-cache.${arch}"
mkdir -p "$BUILD_DIR" "$POETRY_CACHE_DIR" "$CCACHE_DIR" "$RUYI_DIST_CACHE_DIR"

docker_args=(
    --rm
    --platform "linux/${arch}"
    -v "$REPO_ROOT":/home/b/ruyi
    -v "$BUILD_DIR":/build
    -v "$POETRY_CACHE_DIR":/poetry-cache
    -v "$CCACHE_DIR":/ccache
    -v "$RUYI_DIST_CACHE_DIR":/ruyi-dist-cache
    -e RUYI_DIST_INNER=x
)

# only allocate pty if currently running interactively
# check if stdout is a tty
if [[ -t 1 ]]; then
    docker_args+=( -t )
fi

docker_args+=(
    "$(image_tag_base "$arch")"
    /home/b/ruyi/scripts/dist.sh
)

exec docker run "${docker_args[@]}"
