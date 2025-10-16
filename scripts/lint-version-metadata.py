#!/usr/bin/env python3

import ast
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

    ret = lint_ruyi_version_str("ruyi/version.py", poetry2_version)
    if ret:
        print(
            "info: hint, if you want to refactor RUYI_SEMVER, you need to make changes to this lint too"
        )
        sys.exit(ret)


def lint_ruyi_version_str(filename: str, expected_ver: str) -> int:
    with open(filename, "rb") as fp:
        contents = fp.read()

    module = ast.parse(contents, filename)
    found_ver: str | None = None
    for stmt in module.body:
        if not isinstance(stmt, ast.AnnAssign):
            continue
        if not isinstance(stmt.target, ast.Name):
            continue
        if stmt.target.id == "RUYI_SEMVER":
            if not isinstance(stmt.value, ast.Constant):
                print("fatal error: RUYI_SEMVER not a constant")
                return 1
            if not isinstance(stmt.value.value, str):
                print("fatal error: RUYI_SEMVER not a string")
                return 1
            found_ver = stmt.value.value

    if found_ver is None:
        print("fatal error: RUYI_SEMVER annotation assignment not found")
        return 1

    if found_ver != expected_ver:
        print(
            "fatal error: ruyi.version.RUYI_SEMVER inconsistent with primary data source"
        )
        print(f"info: primary pyproject.toml has project.version = '{expected_ver}'")
        print(f"info: ruyi.version.RUYI_SEMVER = '{found_ver}'")
        return 1

    print("info: ruyi.version.RUYI_SEMVER consistent with primary metadata")
    return 0


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
