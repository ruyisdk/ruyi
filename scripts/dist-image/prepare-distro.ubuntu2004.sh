#!/bin/bash

set -e

groupadd -g "$BUILDER_GID" b
useradd -d /home/b -m -g "$BUILDER_GID" -u "$BUILDER_UID" -s /bin/bash b

export DEBIAN_FRONTEND=noninteractive
export DEBCONF_NONINTERACTIVE_SEEN=true

# HTTPS needs ca-certificates to work
sed -i 's@http://archive\.ubuntu\.com/@http://mirrors.huaweicloud.com/@g' /etc/apt/sources.list

# Non-interactive configuration of tzdata
debconf-set-selections <<EOF
tzdata tzdata/Areas select Etc
tzdata tzdata/Zones/Etc select UTC
EOF

apt-get update
apt-get upgrade -qqy
apt-get install -y software-properties-common build-essential patchelf zlib1g-dev ccache
add-apt-repository ppa:deadsnakes/ppa
apt-get install -y python3.11-dev python3.11-venv

apt-get clean
