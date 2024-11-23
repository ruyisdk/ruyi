#!/bin/bash

set -e

cd "$(dirname "${BASH_SOURCE[0]}")"/..
find resources scripts -name '*.sh' -print0 | xargs -0 shellcheck -P . -P scripts
