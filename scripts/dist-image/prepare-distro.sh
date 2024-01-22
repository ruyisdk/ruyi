#!/bin/sh

# we're to be placed here
cd /tmp

# usage: $0 $TARGETARCH
case "$1" in
amd64|arm64)
    exec ./prepare-distro.ubuntu2004.sh
    ;;
riscv64)
    exec ./prepare-distro.debian.sh
    ;;
esac

echo "unrecognized TARGETARCH: $1" >&2
exit 1
