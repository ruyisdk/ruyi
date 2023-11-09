#!/bin/bash

set -e

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

arch="$1"
if [[ -z $arch ]]; then
    echo "usage: $0 <arch>" >&2
    echo >&2
    echo "see scripts/dist-image for available arch choices" >&2
    exit 1
fi

source "$MY_DIR/_image_tag_base.sh"

cd "$MY_DIR/dist-image"
exec docker build --rm \
    --platform "linux/${arch}" \
    -t "$(image_tag_base "$arch")-${arch}" \
    -f "Dockerfile.${arch}" \
    .
