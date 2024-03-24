#!/usr/bin/env python3

import os
import pathlib
import shutil
import subprocess
import sys
import time
import tomllib
from typing import cast

from pygit2.repository import Repository
from rich.console import Console
import semver

# it seems force_terminal is needed for colors to show up on GHA
INFO = Console(stderr=True, style="bold green", force_terminal=True, highlight=False)

LGPL_MODULES = ("xdg",)


def main() -> None:
    epoch = int(time.time())

    vers = get_versions()
    INFO.print(f"Project Git commit       : [cyan]{vers['git_commit']}")
    INFO.print(f"Project SemVer           : [cyan]{vers['semver']}")
    INFO.print(f"Version for use by Nuitka: [cyan]{vers['nuitka_ver']}")

    build_root = "/build"
    exe_name = "ruyi.exe" if sys.platform == "win32" else "ruyi"
    output_file = os.path.join(build_root, exe_name)

    cache_root = "/ruyi-dist-cache"
    ensure_dir(cache_root)

    cache_key = get_cache_key(vers["git_commit"])
    cached_output_dir = pathlib.Path(cache_root) / cache_key
    cached_output_file = cached_output_dir / exe_name
    try:
        shutil.copyfile(cached_output_file, output_file)
        os.chmod(output_file, 0o755)
        INFO.print(f"cache hit at [cyan]{cached_output_file}[/], skipping build")
        return
    except FileNotFoundError:
        pass

    ext_outdir = "/build/_exts"
    ensure_dir(ext_outdir)
    add_pythonpath(ext_outdir)

    # Compile LGPL module(s) into own extensions
    INFO.print("\nBuilding LGPL extension(s)\n")
    for name in LGPL_MODULES:
        make_nuitka_ext(name, ext_outdir)

    # Finally the main program
    INFO.print("\nBuilding Ruyi executable\n")
    begin_group("Building Ruyi executable")
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
    end_group()

    begin_group("Cache maintenance")
    INFO.print(f"\ncaching output to [cyan]{cached_output_file}")
    ensure_dir(cached_output_dir)
    shutil.copyfile(output_file, cached_output_file)
    os.chmod(cached_output_file, 0o755)
    ts = cached_output_dir / "timestamp"
    ts.write_text(f"{epoch}\n")

    delete_cached_files_older_than_days(cache_root, 21, epoch)
    end_group()

    if "GITHUB_ACTIONS" in os.environ:
        set_release_mirror_url_for_gha(vers["semver"])


def is_in_gha() -> bool:
    return "GITHUB_ACTIONS" in os.environ


def begin_group(title: str) -> None:
    if is_in_gha():
        print(f"::group::{title}", flush=True)


def end_group() -> None:
    if is_in_gha():
        print("::endgroup::", flush=True)


def ensure_dir(d: str | pathlib.Path) -> None:
    try:
        os.mkdir(d)
    except FileExistsError:
        pass


def get_cache_key(git_commit: str) -> str:
    return f"ruyi-g{git_commit}"


def delete_cached_files_older_than_days(root: str, days: int, epoch: int) -> None:
    max_ts_delta = days * 86400

    epoch_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))
    INFO.print(
        f"purging cache contents older than [cyan]{days}[/] days from [cyan]now={epoch_str}"
    )

    root_path = pathlib.Path(root)
    dirs_to_remove: list[tuple[pathlib.Path, int | None]] = []
    for f in root_path.iterdir():
        if f.name.startswith("pygit2"):
            INFO.print(f"ignoring pygit2 cache [cyan]{f}")
            continue

        ts: int | None
        try:
            ts = int((f / "timestamp").read_text().strip(), 10)
        except (FileNotFoundError, ValueError):
            dirs_to_remove.append((f, None))
            continue

        if ts - epoch >= max_ts_delta:
            dirs_to_remove.append((f, ts))

    for f, ts in dirs_to_remove:
        if ts is None:
            INFO.print(
                f"removing [cyan]{f}[/] ([yellow]timestamp absent or invalid)[/]"
            )
        else:
            ts_time = time.gmtime(ts)
            ts_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", ts_time)
            INFO.print(f"removing [cyan]{f}[/] (created [yellow]{ts_str}[/])")

        shutil.rmtree(f)


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
    mod_dir = os.path.dirname(cast(str, mod.__file__))
    INFO.print(f"Building [cyan]{module_name}[/] at [cyan]{mod_dir}[/] into extension")
    begin_group(f"Building {module_name} into extension")
    call_nuitka(
        "--module",
        mod_dir,
        f"--include-package={module_name}",
        f"--output-dir={out_dir}",
    )
    end_group()


def get_versions() -> dict[str, str]:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("pyproject.toml", "rb") as fp:
        pyproject = tomllib.load(fp)

    version = pyproject["tool"]["poetry"]["version"]

    return {
        "git_commit": get_git_commit(),
        "semver": version,
        "nuitka_ver": to_version_for_nuitka(version),
    }


def get_git_commit() -> str:
    repo = Repository(".")
    return str(repo.head.target)


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
