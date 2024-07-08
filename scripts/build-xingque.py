#!/usr/bin/env python3

import os
import shutil
import subprocess
import sys
import tomllib
from typing import cast


def get_xingque_src_uri(tag: str) -> tuple[str, str]:
    filename = f"{tag}.tar.gz"
    return (filename, f"https://github.com/xen0n/xingque/archive/refs/tags/{filename}")


def log(s: str, fgcolor: int = 32, group: bool = False) -> None:
    # we cannot import rich because this script is executed before
    # `poetry install` in the dist build process
    print(f"\x1b[1;{fgcolor}m{s}\x1b[m", file=sys.stderr, flush=True)
    if group:
        begin_group(s)


def is_in_gha() -> bool:
    return "GITHUB_ACTIONS" in os.environ


def begin_group(title: str) -> None:
    if is_in_gha():
        print(f"::group::{title}", flush=True)


def end_group() -> None:
    if is_in_gha():
        print("::endgroup::", flush=True)


def main() -> None:
    build_root = os.environ["BUILD_DIR"]

    workdir = os.path.join(build_root, "ruyi-xingque")
    ensure_dir(workdir)

    cache_root = os.environ["RUYI_DIST_CACHE_DIR"]
    ensure_dir(cache_root)

    xingque_ver = get_xingque_version()
    log(f"resolved xingque version {xingque_ver}")

    xingque_cache_rev = 1  # bump this to force rebuild (e.g. for bumping indirect deps)
    xingque_wheel_path = ensure_xingque_wheel(
        xingque_ver,
        workdir,
        cache_root,
        xingque_cache_rev,
    )

    # this will print a header suitable for our logging purposes
    begin_group("pip install the xingque wheel")
    subprocess.run(("pip", "install", xingque_wheel_path), check=True)
    end_group()

    log("informing poetry about the wheel", group=True)
    subprocess.run(("poetry", "add", "--lock", xingque_wheel_path), check=True)
    end_group()


def ensure_dir(d: str) -> None:
    try:
        os.mkdir(d)
    except FileExistsError:
        pass


def ensure_xingque_wheel(
    ver: str, workdir: str, cache_root: str, cache_rev: int
) -> str:
    cache_key = get_cache_key("xingque", ver, cache_rev)
    cache_dir = os.path.join(cache_root, cache_key)
    try:
        wheel_file = [
            i for i in os.listdir(cache_dir) if os.path.splitext(i)[1] == ".whl"
        ][0]
        wheel_path = os.path.join(cache_dir, wheel_file)
        log(f"found cached xingque (cache rev {cache_rev}) at {wheel_path}")
    except (FileNotFoundError, IndexError):
        log(f"cached xingque (cache rev {cache_rev}) not found, building")
        wheel_path = build_xingque(ver, workdir)

        log(f"caching built wheel {wheel_path} to {cache_dir}")
        ensure_dir(cache_dir)

        dest_path = os.path.join(cache_dir, os.path.basename(wheel_path))
        shutil.copyfile(wheel_path, dest_path)

    return wheel_path


def build_xingque(xingque_ver: str, workdir: str) -> str:
    xingque_tag = xingque_ver
    xingque_src_filename, xingque_src_uri = get_xingque_src_uri(xingque_tag)
    xingque_workdir = os.path.join(workdir, f"xingque-{xingque_ver}")

    # download the source
    log(f"downloading {xingque_src_uri}", group=True)
    subprocess.run(
        ("wget", "-O", xingque_src_filename, xingque_src_uri),
        cwd=workdir,
        check=True,
    )
    end_group()

    # unpack the source
    log(f"unpacking {xingque_src_filename}")
    subprocess.run(("tar", "-xf", xingque_src_filename), cwd=workdir, check=True)

    # build wheel
    log("building xingque wheel", group=True)
    subprocess.run(
        ("maturin", "build", "--release"),
        cwd=xingque_workdir,
        check=True,
    )
    maturin_out_path = os.path.join(xingque_workdir, "target", "wheels")
    tmp_wheel_path = os.path.join(
        maturin_out_path,
        find_built_wheel_name_in(maturin_out_path),
    )
    subprocess.run(
        ("auditwheel", "repair", tmp_wheel_path),
        cwd=xingque_workdir,
        check=True,
    )
    end_group()

    xingque_distdir = os.path.join(xingque_workdir, "wheelhouse")
    xingque_wheel_name = find_built_wheel_name_in(xingque_distdir)
    return os.path.join(xingque_distdir, xingque_wheel_name)


def get_xingque_version() -> str:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("poetry.lock", "rb") as fp:
        info = tomllib.load(fp)

    xingque = [pkg for pkg in info["package"] if pkg["name"] == "xingque"][0]
    return cast(str, xingque["version"])


def find_built_wheel_name_in(path: str) -> str:
    return [x for x in os.listdir(path) if os.path.splitext(x)[1] == ".whl"][0]


def get_cache_key(pkg_name: str, version: str, cache_rev: int) -> str:
    return f"{pkg_name}-{version}-cache{cache_rev}"


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
