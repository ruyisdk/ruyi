import argparse
import importlib.metadata

import packaging.version
import semver

from .. import log


def cli_version(args: argparse.Namespace) -> int:
    pkg_pypi_ver = packaging.version.Version(importlib.metadata.version("ruyi"))
    log.D(f"PyPI-style version of ruyi: {pkg_pypi_ver}")
    recovered_semver = convert2semver(pkg_pypi_ver)
    print(f"Ruyi {str(recovered_semver)}")

    return 0


PYPI_PRERELEASE_KINDS_MAP = {
    "a": "alpha",
    "b": "beta",
    "rc": "rc",
}


# based on https://python-semver.readthedocs.io/en/3.0.2/advanced/convert-pypi-to-semver.html
def convert2semver(ver: packaging.version.Version) -> semver.Version:
    log.D(f"epoch {ver.epoch} pre {ver.pre} post {ver.post}")
    if ver.epoch:
        raise ValueError("Can't convert an epoch to semver")
    if ver.post:
        raise ValueError("Can't convert a post part to semver")

    pre: str | None = None
    if ver.pre:
        kind, val = ver.pre
        pre = f"{PYPI_PRERELEASE_KINDS_MAP.get(kind, kind)}.{val}"

    return semver.Version(*ver.release, prerelease=pre, build=ver.dev)
