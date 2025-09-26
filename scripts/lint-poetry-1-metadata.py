#!/usr/bin/env python3

import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def main() -> None:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("pyproject.toml", "rb") as fp:
        poetry2_project = tomllib.load(fp)
        poetry2_version = poetry2_project["project"]["version"]

    with open("contrib/poetry-1.x/pyproject.toml", "rb") as fp:
        poetry1_project = tomllib.load(fp)
        poetry1_version = poetry1_project["tool"]["poetry"]["version"]

    if poetry1_version != poetry2_version:
        print("fatal error: Poetry 1.x metadata inconsistent with primary data source")
        print(f"info: primary pyproject.toml has project.version = '{poetry2_version}'")
        print(f"info: Poetry 1.x has tool.poetry.version = '{poetry1_version}'")
        sys.exit(1)

    print("info: project version consistent between primary and Poetry 1.x metadata")


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
