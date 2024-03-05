#!/usr/bin/env python3

import os
import subprocess
import sys
import tomllib

import semver


LGPL_MODULES = ("xdg",)


def main() -> None:
    vers = get_versions()
    print(f"Project SemVer       : {vers['semver']}")
    print(f"Nuitka version to use: {vers['nuitka_ver']}\n", flush=True)

    ext_outdir = "/build/_exts"
    try:
        os.mkdir(ext_outdir)
    except FileExistsError:
        pass
    add_pythonpath(ext_outdir)

    # Compile LGPL module(s) into own extensions
    print("Building LGPL extension(s)\n", flush=True)
    for name in LGPL_MODULES:
        make_nuitka_ext(name, ext_outdir)

    # Finally the main program
    print("Building Ruyi executable\n", flush=True)
    call_nuitka(
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
        "--include-package=_cffi_backend",  # https://github.com/Nuitka/Nuitka/issues/2505
        "--windows-icon-from-ico=resources/ruyi.ico",
        "./ruyi/__main__.py",
    )


def call_nuitka(*args: str) -> None:
    nuitka_args = [
        # https://stackoverflow.com/questions/64761870/python-subprocess-doesnt-inherit-virtual-environment
        sys.executable,  # "python",
        "-m",
        "nuitka",
    ]
    nuitka_args.extend(args)
    subprocess.run(nuitka_args)


def add_pythonpath(path: str) -> None:
    old_path = os.environ.get("PYTHONPATH", "")
    new_path = path if not old_path else f"{path}{os.pathsep}{old_path}"
    os.environ["PYTHONPATH"] = new_path


def make_nuitka_ext(module_name: str, out_dir: str) -> None:
    mod = __import__(module_name)
    mod_dir = os.path.dirname(mod.__file__)
    print(f"Building {module_name} at {mod_dir} into extension", flush=True)
    call_nuitka(
        "--module",
        mod_dir,
        f"--include-package={module_name}",
        f"--output-dir={out_dir}",
    )


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
