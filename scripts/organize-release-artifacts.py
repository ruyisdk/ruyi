#!/usr/bin/env python3

import os
import pathlib
import shutil
import sys
import tomllib


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <release-artifacts-dir>", file=sys.stderr)
        return 1

    workdir = pathlib.Path(argv[1]).resolve()

    project_root = (pathlib.Path(os.path.dirname(__file__)) / "..").resolve()
    with open(project_root / "pyproject.toml", "rb") as fp:
        pyproject = tomllib.load(fp)

    version = pyproject["tool"]["poetry"]["version"]

    # layout of release-artifacts-dir just after the download-artifacts@v4
    # action:
    #
    # release-artifacts-dir
    # ├── ruyi.amd64
    # │   └── ruyi
    # ├── ruyi.arm64
    # │   └── ruyi
    # ├── ruyi.riscv64
    # │   └── ruyi
    # └── ruyi.windows-amd64.exe
    #     └── ruyi.exe
    #
    # we want to organize it into the following layout:
    #
    # release-artifacts-dir
    # ├── ruyi-<semver>.amd64
    # ├── ruyi-<semver>.arm64
    # └── ruyi-<semver>.riscv64
    #
    # i.e. with the non-Linux build removed, with the directory structure
    # flattened, and with the semver attached.

    os.chdir(workdir)

    # for now, hardcode the exact artifacts we want
    included_arches = ("amd64", "arm64", "riscv64")
    wanted_names = {f"ruyi.{arch}" for arch in included_arches}
    names = os.listdir(".")
    for name in names:
        if not name.startswith("ruyi"):
            print(f"ignoring {name}")
            continue

        if name not in wanted_names:
            print(f"removing unwanted {name}")
            shutil.rmtree(name)
            continue

        # assume name is ruyi.{arch}
        arch = name.rsplit(".", 1)[1]
        src_name = os.path.join(name, "ruyi")
        dest_name = f"ruyi-{version}.{arch}"
        print(f"moving {src_name} to {dest_name}")
        os.rename(src_name, dest_name)
        os.chmod(dest_name, 0o755)
        os.rmdir(name)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
