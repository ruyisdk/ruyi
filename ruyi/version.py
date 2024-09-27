import importlib.metadata

import packaging.version
import semver

# NOTE: one cannot print logs in the version helpers, because the version info
# is initialized so early (before argparse can look at argv because --version
# requires version info to be ready) that the porcelain status is not yet
# available.

PYPI_PRERELEASE_KINDS_MAP = {
    "a": "alpha",
    "b": "beta",
    "rc": "rc",
}


# based on https://python-semver.readthedocs.io/en/3.0.2/advanced/convert-pypi-to-semver.html
def convert2semver(ver: packaging.version.Version) -> semver.Version:
    if ver.epoch:
        raise ValueError("Can't convert an epoch to semver")
    if ver.post:
        raise ValueError("Can't convert a post part to semver")

    pre: str | None = None
    if ver.pre:
        kind, val = ver.pre
        pre = f"{PYPI_PRERELEASE_KINDS_MAP.get(kind, kind)}.{val}"

    maj, min, pat = ver.release[:3]
    return semver.Version(maj, min, pat, prerelease=pre, build=ver.dev)


def init_pkg_semver() -> semver.Version:
    pkg_pypi_ver = packaging.version.Version(importlib.metadata.version("ruyi"))
    # log.D(f"PyPI-style version of ruyi: {pkg_pypi_ver}")
    return convert2semver(pkg_pypi_ver)


RUYI_SEMVER = init_pkg_semver()


COPYRIGHT_NOTICE = """\
Copyright (C) 2023 Institute of Software, Chinese Academy of Sciences (ISCAS).
All rights reserved.
License: Apache-2.0 <https://www.apache.org/licenses/LICENSE-2.0>

This version of ruyi makes use of code licensed under the Mozilla Public
License 2.0 (https://mozilla.org/MPL/2.0/). You can get the respective
project's sources from the project's official website:

* certifi: https://github.com/certifi/python-certifi
\
"""
