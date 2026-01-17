#!/bin/bash

set -e

main() {
    local pkglist=(
        # Package versions provided by Ubuntu 22.04 LTS.
        python3-argcomplete  # 3.1.4
        python3-arpy  # 1.1.1
        python3-babel  # 2.8.0
        python3-certifi  # 2020.6.20
        python3-fastjsonschema  # 2.15.1
        python3-jinja2  # 3.0.3
        python3-pygit2  # 1.6.1
        python3-yaml  # 5.4.1  # https://github.com/yaml/pyyaml/issues/724
        python3-requests  # 2.25.1
        python3-rich  # 11.2.0
        python3-semver  # 2.10.2
        python3-tomli  # 1.2.2
        python3-tomlkit  # 0.9.2
        python3-typing-extensions  # 3.10.0.2

        # for installing ourselves
        python3-pip

        # for running the test suite with purely system deps
        python3-pytest  # 6.2.5
    )

    export DEBIAN_FRONTEND=noninteractive
    export DEBCONF_NONINTERACTIVE_SEEN=true
    sudo apt-get update -qqy
    sudo apt-get install -y "${pkglist[@]}"
}

main "$@"
