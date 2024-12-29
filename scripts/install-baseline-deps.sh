#!/bin/bash

set -e

MY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

main() {
    local requirements_file="$MY_DIR/requirements.baseline.txt"

    # Install pygit2 build deps -- prebuilt 1.6.1 wheels on PyPI are only
    # available for Python up to 3.9.
    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    sudo apt-get update -qqy
    sudo apt-get install -qqy libgit2-dev

    # Workaround https://github.com/yaml/pyyaml/issues/724 because we need
    # exactly this version of PyYAML for faithful reproduction of the baseline
    # environment.
    poetry run pip install 'Cython<3'
    poetry run pip install --no-build-isolation 'PyYAML==5.4.1'

    poetry run pip install -r "$requirements_file"
}

main "$@"
