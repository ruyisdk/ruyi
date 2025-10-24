#!/bin/bash

set -e

# Nuitka now requires final versions of Python, but unfortunately the python3.11
# in the jammy repo is 3.11.0rc1, and there's no python3.12 in repo, so we have
# to build our own Python for now.
#
# See: https://github.com/Nuitka/Nuitka/commit/54f2a2222abedf92d45b8f397233cfb3bef340c5

PYTHON_V=3.13.9
pushd /tmp
wget "https://www.python.org/ftp/python/${PYTHON_V}/Python-${PYTHON_V}.tar.xz"
mkdir py-src py-build
tar -xf "Python-${PYTHON_V}.tar.xz" --strip-components=1 -C py-src

pushd py-build
../py-src/configure --prefix=/usr/local
make -j
make install
popd

rm -rf py-src py-build Python-*.tar.xz
popd
