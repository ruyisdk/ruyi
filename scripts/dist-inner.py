#!/usr/bin/env python3

import os
import subprocess
import sys
import tomllib

from rich.console import Console
import semver

# it seems force_terminal is needed for colors to show up on GHA
INFO = Console(stderr=True, style="bold green", force_terminal=True)

LGPL_MODULES = ("xdg",)


def main() -> None:
    vers = get_versions()
    INFO.print(f"Project SemVer       : [cyan]{vers['semver']}")
    INFO.print(f"Nuitka version to use: [cyan]{vers['nuitka_ver']}")

    ext_outdir = "/build/_exts"
    try:
        os.mkdir(ext_outdir)
    except FileExistsError:
        pass
    add_pythonpath(ext_outdir)

    # Compile LGPL module(s) into own extensions
    INFO.print("\nBuilding LGPL extension(s)\n")
    for name in LGPL_MODULES:
        make_nuitka_ext(name, ext_outdir)

    # Finally the main program
    INFO.print("\nBuilding Ruyi executable\n")
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

    if "GITHUB_ACTIONS" in os.environ:
        set_release_mirror_url_for_gha(vers["semver"])


def call_nuitka(*args: str) -> None:
    nuitka_args = [
        # https://stackoverflow.com/questions/64761870/python-subprocess-doesnt-inherit-virtual-environment
        sys.executable,  # "python",
        "-m",
        "nuitka",
    ]
    nuitka_args.extend(args)
    subprocess.run(nuitka_args, check=True)


def add_pythonpath(path: str) -> None:
    old_path = os.environ.get("PYTHONPATH", "")
    new_path = path if not old_path else f"{path}{os.pathsep}{old_path}"
    os.environ["PYTHONPATH"] = new_path


def make_nuitka_ext(module_name: str, out_dir: str) -> None:
    mod = __import__(module_name)
    mod_dir = os.path.dirname(mod.__file__)
    INFO.print(f"Building [cyan]{module_name}[/] at [cyan]{mod_dir}[/] into extension")
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


def set_release_mirror_url_for_gha(version: str) -> None:
    release_url_base = "https://mirror.iscas.ac.cn/ruyisdk/ruyi/releases/"
    testing_url_base = "https://mirror.iscas.ac.cn/ruyisdk/ruyi/testing/"

    sv = semver.Version.parse(version)
    url_base = testing_url_base if sv.prerelease else release_url_base
    url = f"{url_base}{version}/"
    set_gha_output("release_mirror_url", url)


def set_gha_output(k: str, v: str) -> None:
    if "\n" in v:
        raise ValueError("this helper is only for small one-line outputs")

    # only do this when the GitHub Actions output file is available
    # https://docs.github.com/en/actions/using-workflows/workflow-commands-for-github-actions#setting-an-output-parameter
    outfile = os.environ.get("GITHUB_OUTPUT", "")
    if not outfile:
        return

    INFO.print(f"GHA: setting output [cyan]{k}[/] to [cyan]{v}[/]")
    with open(outfile, "a") as fp:
        fp.write(f"{k}={v}\n")


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
