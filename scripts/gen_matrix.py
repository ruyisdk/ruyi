#!/usr/bin/env python3

import os
import json
import pathlib
import pprint
import sys
from typing import NamedTuple, TypedDict


def log(s: str, fgcolor: int = 32) -> None:
    # we cannot import rich because this script is executed before
    # `poetry install` in the dist build process
    print(f"\x1b[1;{fgcolor}m{s}\x1b[m", file=sys.stderr, flush=True)


class Combo(NamedTuple):
    os: str
    arch: str
    self_hosted: bool
    run_on_pr: bool


RunsOn = str | list[str]


class MatrixEntry(TypedDict):
    arch: str
    build_output_name: str
    is_windows: bool
    job_name: str
    runs_on: RunsOn
    upload_artifact_name: str


def runs_on(c: Combo) -> RunsOn:
    if c.self_hosted:
        return ["self-hosted", c.os, c.arch]
    match c.os:
        case "linux":
            return "ubuntu-latest"
        case "windows":
            return "windows-latest"
    raise ValueError(f"unrecognized combo {c} for deriving runs_on property")


def upload_artifact_name(c: Combo) -> str:
    if c.os == "windows":
        return f"ruyi.windows-{c.arch}.exe"
    return f"ruyi.{c.arch}"


def build_output_name(c: Combo) -> str:
    return "ruyi.exe" if c.os == "windows" else "ruyi"


def to_matrix_entry(c: Combo) -> MatrixEntry:
    return {
        "arch": c.arch,
        "build_output_name": build_output_name(c),
        "is_windows": c.os == "windows",
        "job_name": f"{c.os.title()} {c.arch}",
        "runs_on": runs_on(c),
        "upload_artifact_name": upload_artifact_name(c),
    }


class MatrixFilter:
    def __init__(self, ref: str, event_name: str, os: str) -> None:
        self.ref = ref
        self.event_name = event_name
        self.os = os

    def should_run(self, c: Combo) -> bool:
        if c.os != self.os:
            return False
        return c.run_on_pr if self.event_name == "pull_request" else True


COMBOS: list[Combo] = [
    Combo("linux", "amd64", False, True),
    Combo("linux", "arm64", True, False),
    Combo("linux", "riscv64", True, False),
    Combo("windows", "amd64", False, False),
]


def main() -> None:
    # https://docs.github.com/en/actions/learn-github-actions/variables
    gh_ref = os.environ["GITHUB_REF"]
    gh_event = os.environ["GITHUB_EVENT_NAME"]
    log(f"GITHUB_REF={gh_ref}")
    log(f"GITHUB_EVENT_NAME={gh_event}")
    mf = MatrixFilter(gh_ref, gh_event, sys.argv[1])

    result_includes = [to_matrix_entry(c) for c in COMBOS if mf.should_run(c)]
    matrix = {"include": result_includes}

    log("resulting matrix:")
    pprint.pprint(matrix)

    outfile = pathlib.Path(os.environ["GITHUB_OUTPUT"])
    outfile.write_text(f"matrix={json.dumps(matrix)}\n")


if __name__ == "__main__":
    main()
