#!/bin/bash

set -e

main() {
    local pkglist=(
        # Package versions provided by Ubuntu 24.04 LTS.
        python3-argcomplete  # 3.1.4
        python3-arpy  # 1.1.1
        python3-babel  # 2.10.3
        python3-certifi  # 2023.11.17
        python3-fastjsonschema  # 2.19.0
        python3-jinja2  # 3.1.2
        python3-pygit2  # 1.14.1
        python3-requests  # 2.31.0
        python3-rich  # 13.7.1
        python3-semver  # 2.10.2
        python3-tomlkit  # 0.12.4
        python3-typing-extensions  # 4.10.0
        python3-yaml  # 6.0.1

        # for installing ourselves
        python3-pip

        # for running the test suite with purely system deps
        python3-pytest  # 7.4.4
    )

    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    sudo apt-get update -qqy
    sudo apt-get install -y "${pkglist[@]}"
}

main "$@"
