#!/usr/bin/env python3

import os
import sys
from typing import cast

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def main() -> None:
    v = get_semver()
    set_release_mirror_url_for_gha(v)


def get_semver() -> str:
    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)
    with open("pyproject.toml", "rb") as fp:
        pyproject = tomllib.load(fp)

    return cast(str, pyproject["project"]["version"])


def set_release_mirror_url_for_gha(version: str) -> None:
    release_url_base = "https://mirror.iscas.ac.cn/ruyisdk/ruyi/releases/"
    testing_url_base = "https://mirror.iscas.ac.cn/ruyisdk/ruyi/testing/"

    # Do not depend on external libraries so this can work in plain GHA
    # environment without any venv setup. See the SemVer spec -- as long as
    # we don't have build tags containing "-" we should be fine, which is
    # exactly the case.
    #
    # sv = Version.parse(version)
    # is_prerelease = sv.prerelease
    is_prerelease = "-" in version

    url_base = testing_url_base if is_prerelease else release_url_base
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

    with open(outfile, "a", encoding="utf-8") as fp:
        fp.write(f"{k}={v}\n")


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    main()
