#!/bin/bash

set -e

main() {
    local pkglist=(
        # Package versions provided by Ubuntu 22.04 LTS.
        python3-arpy  # 1.1.1
        python3-certifi  # 2020.6.20
        python3-jinja2  # 3.0.3
        python3-packaging  # 21.3
        python3-pygit2  # 1.6.1
        python3-yaml  # 5.4.1  # https://github.com/yaml/pyyaml/issues/724
        python3-requests  # 2.25.1
        python3-rich  # 11.2.0
        python3-semver  # 2.10.2
        python3-tomli  # 1.2.2
        python3-tomlkit  # 0.9.2
        python3-typing-extensions  # 3.10.0.2
    )

    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    sudo apt-get update -qqy
    sudo apt-get install -y "${pkglist[@]}"

    # we need a recent pytest for running the tests though
    pipx install pytest
}

main "$@"
