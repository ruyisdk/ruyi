#!/bin/bash

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)"
TMPDIR=''

_cleanup() {
    [[ -n $TMPDIR ]] && rm -rf "$TMPDIR"
}

get_repo_commit_time() {
    TZ=UTC0 git log -1 --format='tformat:%cd' --date='format:%Y-%m-%dT%H:%M:%SZ'
}

reproducible_tar() {
    local args=(
        --sort=name
        --format=posix
        --pax-option='exthdr.name=%d/PaxHeaders/%f'
        --pax-option='delete=atime,delete=ctime'
        --clamp-mtime
        --mtime="$SOURCE_EPOCH"
        --numeric-owner
        --owner=0
        --group=0
        "$@"
    )

    LC_ALL=C tar "${args[@]}"
}

# shellcheck disable=SC2120
reproducible_gzip() {
    gzip -9 -n "$@"
}

main() {
    local version source_epoch staging_dirname dest_dir

    cd "$REPO_ROOT"
    version="$(git describe)"
    source_epoch="$(get_repo_commit_time)"
    staging_dirname="ruyi-$version"
    artifact_name="$staging_dirname.tar.gz"
    dest_dir="${1:=$REPO_ROOT/tmp}"

    TMPDIR="$(mktemp -d)"
    trap _cleanup EXIT

    git clone --recurse-submodules "$REPO_ROOT" "$TMPDIR/$staging_dirname"
    pushd "$TMPDIR/$staging_dirname" > /dev/null
    # remove Git metadata
    find . -name .git -exec rm -rf '{}' '+'
    # set all file timestamps to $SOURCE_EPOCH
    find . -exec touch -md "$source_epoch" '{}' '+'
    popd > /dev/null

    pushd "$TMPDIR" > /dev/null
    reproducible_tar -cf - "./$staging_dirname" | reproducible_gzip > "$dest_dir/$artifact_name"
    popd > /dev/null

    echo "info: repo HEAD content is reproducibly packed at $dest_dir/$artifact_name"
    [[ -n $GITHUB_OUTPUT ]] && echo "artifact_name=$artifact_name" > "$GITHUB_OUTPUT"
}

main "$@"
