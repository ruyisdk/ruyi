#!/usr/bin/env python3

# meant for eval-ing inside dist-inner.sh only
# expects CWD to be project root

import shlex
import tomllib

import semver


def main() -> None:
    with open("pyproject.toml", "rb") as fp:
        pyproject = tomllib.load(fp)

    version = pyproject["tool"]["poetry"]["version"]
    print(f"RUYI_DIST_SEMVER={shlex.quote(version)}")
    print(f"RUYI_DIST_NUITKA_VER={shlex.quote(to_version_for_nuitka(version))}")


PRERELEASE_NUITKA_PATCH_VER_MAP = {
    "alpha": 10000,
    "beta": 20000,
    "rc": 30000,
}


def to_version_for_nuitka(version: str) -> str:
    """
    Figure out the Windows-style version string for Nuitka, from the input
    semver string.

    * `X.Y.Z` -> `X.Y.Z.0`
    * `X.Y.Z-alpha.YYYYMMDD` -> `X.(Y-1).1YYYY.MMDD0`
    * `X.Y.Z-beta.YYYYMMDD` -> `X.(Y-1).2YYYY.MMDD0`
    * `X.Y.Z-rc.YYYYMMDD` -> `X.(Y-1).3YYYY.MMDD0`

    The strange mapping is due to Nuitka (actually Windows?) requiring each
    part to fit in an u16.
    """

    sv = semver.Version.parse(version)
    if not sv.prerelease:
        return f"{version}.0"

    n_major = sv.major
    n_minor = sv.minor - 1
    prerelease_kind, ymd_str = sv.prerelease.split(".")
    y, md = divmod(int(ymd_str), 10000)
    n_patch = PRERELEASE_NUITKA_PATCH_VER_MAP[prerelease_kind] + y
    n_extra = md * 10
    return f"{n_major}.{n_minor}.{n_patch}.{n_extra}"


if __name__ == "__main__":
    main()
