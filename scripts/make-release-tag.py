#!/usr/bin/env python3

import os
import pathlib
import subprocess
import sys
from typing import NoReturn

from pygit2 import Repository
from tomlkit_extras import TOMLDocumentDescriptor, load_toml_file


try:
    from semver.version import Version  # type: ignore[import-untyped,unused-ignore]
except ModuleNotFoundError:
    from semver import VersionInfo as Version  # type: ignore[import-untyped,unused-ignore]


def render_tag_message(version: str) -> str:
    return f"Ruyi {version}"


def fatal(msg: str) -> NoReturn:
    print(f"fatal: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    pyproject = load_toml_file(pathlib.Path("pyproject.toml"))
    pyproject_desc = TOMLDocumentDescriptor(pyproject)

    project_table = pyproject_desc.get_table("project")
    version_field = project_table.fields["version"]
    lineno = version_field.line_no
    version = version_field.value
    if not isinstance(version, str):
        fatal(f"expected project.version to be a string, got {type(version)}")

    # Check if the version is a valid semver version
    try:
        Version.parse(version)
    except ValueError as e:
        fatal(f"invalid semver {version} in pyproject.toml: {e}")

    print(f"info: project version is {version}, defined at pyproject.toml:{lineno}")

    # Check if the tag is already present
    repo = Repository(".")
    try:
        tag_ref = repo.lookup_reference(f"refs/tags/{version}")
    except KeyError:
        tag_ref = None

    if tag_ref is not None:
        print(f"info: tag {version} already exists")
        # idempotence: don't fail the workflow with non-zero status code
        sys.exit(0)

    # Blame pyproject.toml to find the commit bumping the version
    blame = repo.blame("pyproject.toml")
    ver_bump_commit_id = blame.for_line(lineno).final_commit_id
    print(f"info: the version-bumping commit is {ver_bump_commit_id}")

    ver_bump_commit = repo.get(ver_bump_commit_id)
    if ver_bump_commit is None:
        fatal(f"could not find version-bumping commit {ver_bump_commit_id}")

    # Create the tag with Git command line to allow for GPG signing
    argv = ["git", "tag", "-m", render_tag_message(version)]

    if "RUYI_NO_GPG_SIGN" in os.environ:
        argv.extend(["-a", "--no-sign"])
    else:
        argv.append("-s")

    argv.extend([version, str(ver_bump_commit_id)])

    print(f"info: invoking git: {' '.join(argv)}")
    subprocess.run(argv, check=True)

    print(f"info: tag {version} created successfully")
    sys.exit(0)


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
