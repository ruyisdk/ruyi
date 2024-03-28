#!/bin/bash

set -e

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
    export POETRY_CACHE_DIR=/poetry-cache
    export CCACHE_DIR=/ccache
    export MAKEFLAGS="-j$(nproc)"

    cd /home/b
    . ./venv/bin/activate

    if [[ -n $CI ]]; then
        green "current user info" group
        id
        endgroup
        green "home directory contents" group
        ls -alF .
        endgroup
        green "repo contents" group
        ls -alF ./ruyi
        endgroup
        green "ruyi-dist-cache contents" group
        ls -alF /ruyi-dist-cache
        endgroup

        if [[ ! -O ./ruyi ]]; then
            green "adding the repo to the list of Git safe directories"
            git config --global --add safe.directory "$(realpath ./ruyi)"
        fi
    fi

    cd ruyi
    case "$(uname -m)" in
    riscv64)
        ./scripts/build-pygit2.py
        ;;
    esac

    green "installing deps" group
    poetry install --with=dist --without=dev
    endgroup

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
    -i  # required to be able to interrupt the build with ^C
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
