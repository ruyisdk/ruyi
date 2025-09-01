import importlib.metadata
from typing import Final, TYPE_CHECKING

import packaging.version

if TYPE_CHECKING:
    # pyright only works with semver 3.x
    from semver.version import Version
else:
    try:
        from semver.version import Version  # type: ignore[import-untyped,unused-ignore]
    except ModuleNotFoundError:
        # semver 2.x
        from semver import VersionInfo as Version  # type: ignore[import-untyped,unused-ignore]

# NOTE: one cannot print logs in the version helpers, because the version info
# is initialized so early (before argparse can look at argv because --version
# requires version info to be ready) that the porcelain status is not yet
# available.

_PYPI_PRERELEASE_KINDS_MAP: Final = {
    "a": "alpha",
    "b": "beta",
    "rc": "rc",
}


# based on https://python-semver.readthedocs.io/en/3.0.2/advanced/convert-pypi-to-semver.html
def _convert2semver(ver: packaging.version.Version) -> Version:
    if ver.epoch:
        raise ValueError("Can't convert an epoch to semver")
    if ver.post:
        raise ValueError("Can't convert a post part to semver")

    pre: str | None = None
    if ver.pre:
        kind, val = ver.pre
        pre = f"{_PYPI_PRERELEASE_KINDS_MAP.get(kind, kind)}.{val}"

    maj, min, pat = ver.release[:3]
    return Version(maj, min, pat, prerelease=pre, build=ver.dev)


def _init_pkg_semver() -> Version:
    pkg_pypi_ver = packaging.version.Version(importlib.metadata.version("ruyi"))
    # log.D(f"PyPI-style version of ruyi: {pkg_pypi_ver}")
    return _convert2semver(pkg_pypi_ver)


RUYI_SEMVER: Final = _init_pkg_semver()
RUYI_USER_AGENT: Final = f"ruyi/{RUYI_SEMVER}"

COPYRIGHT_NOTICE: Final = """\
Copyright (C) Institute of Software, Chinese Academy of Sciences (ISCAS).
All rights reserved.
License: Apache-2.0 <https://www.apache.org/licenses/LICENSE-2.0>
\
"""

MPL_REDIST_NOTICE: Final = """\
This distribution of ruyi contains code licensed under the Mozilla Public
License 2.0 (https://mozilla.org/MPL/2.0/). You can get the respective
project's sources from the project's official website:

* certifi: https://github.com/certifi/python-certifi
\
"""
