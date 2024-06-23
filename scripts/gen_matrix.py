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


def is_ci_forced_for_all(pr_title: str) -> bool:
    return "[ci force-all]" in pr_title.lower()


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
    skip: bool
    upload_artifact_name: str


def runs_on(c: Combo) -> RunsOn:
    if c.self_hosted:
        return ["self-hosted", c.os, c.arch]
    match c.os:
        case "linux":
            return "ubuntu-latest"
        case "windows":
            return "windows-latest"
        case _:
            raise ValueError(f"unrecognized combo {c} for deriving runs_on property")


def upload_artifact_name(c: Combo) -> str:
    if c.os == "windows":
        return f"ruyi.windows-{c.arch}.exe"
    return f"ruyi.{c.arch}"


def build_output_name(c: Combo) -> str:
    return "ruyi.exe" if c.os == "windows" else "ruyi"


def to_matrix_entry(c: Combo, should_run: bool) -> MatrixEntry:
    return {
        "arch": c.arch,
        "build_output_name": build_output_name(c),
        "is_windows": c.os == "windows",
        "job_name": f"{c.os.title()} {c.arch}",
        "runs_on": runs_on(c),
        "skip": not should_run,
        "upload_artifact_name": upload_artifact_name(c),
    }


class MatrixFilter:
    def __init__(
        self,
        ref: str,
        event_name: str,
        pr_title: str,
        oses: set[str],
    ) -> None:
        self.ref = ref
        self.event_name = event_name
        self.force_all = is_ci_forced_for_all(pr_title)
        self.oses = oses

    def should_include(self, c: Combo) -> bool:
        return c.os in self.oses

    def should_run(self, c: Combo) -> bool:
        if self.event_name == "pull_request":
            return True if self.force_all else c.run_on_pr
        return True


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
    pr_title = os.environ.get("RUYI_PR_TITLE", "")
    log(f"GITHUB_REF={gh_ref}")
    log(f"GITHUB_EVENT_NAME={gh_event}")
    log(f"RUYI_PR_TITLE='{pr_title}'")
    mf = MatrixFilter(gh_ref, gh_event, pr_title, set(sys.argv[1:]))

    result_includes = [
        to_matrix_entry(c, mf.should_run(c)) for c in COMBOS if mf.should_include(c)
    ]

    # GitHub Actions doesn't like it if the matrix is empty, so we have to keep
    # at least one entry for the list, but otherwise we're free to drop the
    # skipped entries.
    #
    # This is useful for reducing CI times because self-hosted runner jobs tend
    # to finish slower even if nothing is to be done, due to the RPC costs.
    # For example, right now the riscv64 runner takes 1min just for the startup
    # and teardown overhead.
    if not all(entry["skip"] for entry in result_includes):
        # At least one job will remain after filtering.
        result_includes = [entry for entry in result_includes if not entry["skip"]]

    matrix = {"include": result_includes}

    log("resulting matrix:")
    for entry in result_includes:
        print(f"::group::Job {entry['job_name']}")
        pprint.pprint(entry)
        print("::endgroup::")

    outfile = pathlib.Path(os.environ["GITHUB_OUTPUT"])
    outfile.write_text(f"matrix={json.dumps(matrix)}\n")


if __name__ == "__main__":
    main()
