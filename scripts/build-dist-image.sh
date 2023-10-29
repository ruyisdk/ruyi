#!/bin/bash

set -e

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$MY_DIR/dist-image"
exec docker build --rm -t ruyi-python-dist:ubuntu2204-20231029 .
