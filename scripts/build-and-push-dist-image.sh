#!/bin/bash

set -e

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$MY_DIR/_image_tag_base.sh"

cd "$MY_DIR/dist-image"
exec docker buildx build --rm \
    --platform "linux/amd64,linux/arm64,linux/riscv64" \
    -t "$(image_tag_base "")" \
    --push \
    .
