import argparse
import importlib.metadata

import packaging.version
import semver

from .. import log


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


def init_pkg_semver() -> semver.Version:
    pkg_pypi_ver = packaging.version.Version(importlib.metadata.version("ruyi"))
    log.D(f"PyPI-style version of ruyi: {pkg_pypi_ver}")
    return convert2semver(pkg_pypi_ver)


RUYI_SEMVER = init_pkg_semver()


def cli_version(_: argparse.Namespace) -> int:
    print(f"Ruyi {RUYI_SEMVER}")

    return 0
