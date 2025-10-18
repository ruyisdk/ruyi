#!/usr/bin/env python3

import argparse
import os
import shutil
import subprocess
import sys
import time

import semver
import tomlkit


OPS_CHOICES = (
    "alpha",  # Make an alpha pre-release
    "beta",  # Make a beta pre-release
    "release",  # Make an official release
    "date",  # Bump the datestamp
    "major",  # Bump the major version
    "minor",  # Bump the minor version
    "patch",  # Bump the patch version
    "commit",  # Actually make the changes and perform `git commit`
)


def main(argv: list[str]) -> int:
    a = argparse.ArgumentParser()
    a.add_argument(
        "ops",
        choices=OPS_CHOICES,
        metavar="OP",
        nargs="+",
        help="Bumping operation to make",
    )

    args = a.parse_args(argv[1:])
    ops: list[str] = args.ops

    # assume CWD is project root, which is guaranteed to be the case (see
    # end of file)

    # first read current version
    with open("pyproject.toml", "rb") as fp:
        pyproject = tomlkit.load(fp)
    curr_ver_str: str = pyproject["project"]["version"]  # type: ignore[assignment,index]
    curr_ver = semver.Version.parse(curr_ver_str)
    prerelease = curr_ver.prerelease

    testing_kind: str | None = None
    datestamp: str | None = None
    if prerelease:
        testing_kind, datestamp = prerelease.split(".", 1)

    new_ver_components = curr_ver.to_dict()
    assert isinstance(new_ver_components["major"], int)
    assert isinstance(new_ver_components["minor"], int)
    assert isinstance(new_ver_components["patch"], int)
    commit = False
    for op in ops:
        match op:
            case "alpha" | "beta" | "date":
                datestamp = time.strftime("%Y%m%d")
                if op != "date":
                    testing_kind = op
                new_ver_components["prerelease"] = f"{testing_kind}.{datestamp}"
            case "release":
                new_ver_components["prerelease"] = None
            case "major":
                new_ver_components["major"] += 1
                new_ver_components["minor"] = 0
                new_ver_components["patch"] = 0
            case "minor":
                new_ver_components["minor"] += 1
                new_ver_components["patch"] = 0
            case "patch":
                new_ver_components["patch"] += 1
            case "commit":
                commit = True
                break
            case _:
                raise NotImplementedError(f"unhandled op '{op}'")

    new_ver = semver.Version(**new_ver_components)  # type: ignore[arg-type]
    new_ver_str = str(new_ver)
    if new_ver_str == curr_ver_str:
        # due to our adoption of CalVer in prerelease numbering, we have
        # to wait for another day if a release of the curr kind is
        # already made today
        print("error: version unchanged after bumping", file=sys.stderr)
        return 1

    if not commit:
        print(f"info: would bump {curr_ver_str} to {new_ver_str}")
        print('info: changes are not made; re-run with "commit" op')
        return 0

    print(f"info: bumping {curr_ver_str} to {new_ver_str}")

    git_path = shutil.which("git")
    if git_path is None:
        print("error: git not found in PATH", file=sys.stderr)
        return 1

    # TODO: ensure staging area is clean before touching files?
    _bump_pyproject_toml("pyproject.toml", pyproject, new_ver_str, False)
    _bump_pyproject_toml("contrib/poetry-1.x/pyproject.toml", None, new_ver_str, True)
    _bump_ruyi_version_py("ruyi/version.py", new_ver_str)

    touched_files = [
        "pyproject.toml",
        "contrib/poetry-1.x/pyproject.toml",
        "ruyi/version.py",
    ]
    subprocess.run([git_path, "add"] + touched_files, check=True)

    if sys.stdin.isatty():
        stdin_target = os.readlink(f"/proc/self/fd/{sys.stdin.fileno()}")
        print(f"info: setting GPG_TTY to {stdin_target} for git commit")
        os.environ["GPG_TTY"] = stdin_target

    commit_title = f"build: bump self version to {new_ver_str}"
    subprocess.run([git_path, "commit", "-s", "-m", commit_title], check=True)

    if sys.stdin.isatty():
        # display the commit we just made for manual inspection, in case
        # something gets unintentionally included, if the current session is
        # interactive
        sys.stdout.flush()
        os.execv(git_path, ["git", "show"])

    return 0


def _bump_pyproject_toml(
    file: str,
    obj: tomlkit.TOMLDocument | None,
    new_ver: str,
    poetry1: bool,
) -> None:
    if obj is None:
        with open(file, "rb") as fp:
            obj = tomlkit.load(fp)

    if poetry1:
        obj["tool"]["poetry"]["version"] = new_ver  # type: ignore[index]
    else:
        obj["project"]["version"] = new_ver  # type: ignore[index]

    with open(file, "wb") as fp:
        fp.write(tomlkit.dumps(obj).encode("utf-8"))


_RUYI_SEMVER_LINE_PREFIX = "RUYI_SEMVER: Final ="


def _bump_ruyi_version_py(file: str, new_ver: str) -> None:
    lines = []
    with open(file, "r") as fp:
        for line in fp:
            if not line.startswith(_RUYI_SEMVER_LINE_PREFIX):
                lines.append(line)
                continue
            # we want an escaped string that's to be quoted with double
            # quotes, but repr() by default gives us single quotes
            new_ver_escaped = repr(new_ver)[1:-1].replace('"', '\\"')
            lines.append(f'{_RUYI_SEMVER_LINE_PREFIX} "{new_ver_escaped}"\n')

    with open(file, "wb") as fp:
        fp.write("".join(lines).encode("utf-8"))


if __name__ == "__main__":
    # cd to project root
    os.chdir(os.path.join(os.path.dirname(__file__), ".."))
    sys.exit(main(sys.argv))
