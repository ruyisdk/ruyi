#!/usr/bin/env python3

import os
import subprocess
import sys
import tomllib

import semver


def main() -> None:
    vers = get_versions()
    print(f"Project SemVer       : {vers['semver']}")
    print(f"Nuitka version to use: {vers['nuitka_ver']}")
    sys.stdout.flush()

    nuitka_args = (
        # https://stackoverflow.com/questions/64761870/python-subprocess-doesnt-inherit-virtual-environment
        sys.executable,  # "python",
        "-m",
        "nuitka",
        "--standalone",
        "--onefile",
        "--assume-yes-for-downloads",
        "--output-filename=ruyi",
        "--output-dir=/build",
        "--no-deployment-flag=self-execution",
        f"--product-version={vers['nuitka_ver']}",
        f"--onefile-tempdir-spec={{CACHE_DIR}}/ruyi/progcache/{vers['semver']}",
        "--include-package=pygments.formatters",
        "--include-package=pygments.lexers",
        "--include-package=pygments.styles",
        "--windows-icon-from-ico=resources/ruyi.ico",
        "./ruyi/__main__.py",
    )

    subprocess.run(nuitka_args)


def get_versions() -> dict[str, str]:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("pyproject.toml", "rb") as fp:
        pyproject = tomllib.load(fp)

    version = pyproject["tool"]["poetry"]["version"]
    return {
        "semver": version,
        "nuitka_ver": to_version_for_nuitka(version),
    }


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
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
