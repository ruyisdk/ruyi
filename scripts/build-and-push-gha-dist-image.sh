#!/bin/bash

set -e

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$MY_DIR/_image_tag_base.sh"

cd "$MY_DIR/dist-image"
for arch in "${!_RUYI_GHA_IMAGE_TAGS[@]}"; do
  echo "building arch $arch"
  arch_tag="${_RUYI_GHA_IMAGE_TAGS[$arch]}"

  docker buildx build --rm \
    --platform "linux/$arch" \
    -t "$arch_tag" \
    --push \
    -f Dockerfile \
    .
done
