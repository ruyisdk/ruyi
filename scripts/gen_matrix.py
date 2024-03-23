#!/usr/bin/env python3

import os
import json
import pathlib
import pprint
import sys
from typing import NamedTuple


def log(s: str, fgcolor: int = 32) -> None:
    # we cannot import rich because this script is executed before
    # `poetry install` in the dist build process
    print(f"\x1b[1;{fgcolor}m{s}\x1b[m", file=sys.stderr, flush=True)


class Combo(NamedTuple):
    os: str
    arch: str
    self_hosted: bool
    run_on_pr: bool


COMBOS: list[Combo] = [
    Combo("linux", "amd64", False, True),
    Combo("linux", "arm64", True, False),
    Combo("linux", "riscv64", True, False),
]


def to_matrix_entry(c: Combo) -> dict[str, object]:
    if c.self_hosted:
        return {"arch": c.arch, "runs_on": ["self-hosted", c.os, c.arch]}
    return {"arch": c.arch, "runs_on": "ubuntu-latest"}


class MatrixFilter:
    def __init__(self, ref: str, event_name: str) -> None:
        self.ref = ref
        self.event_name = event_name

    def should_run(self, c: Combo) -> bool:
        return c.run_on_pr if self.event_name == "pull_request" else True


def main() -> None:
    # https://docs.github.com/en/actions/learn-github-actions/variables
    gh_ref = os.environ["GITHUB_REF"]
    gh_event = os.environ["GITHUB_EVENT_NAME"]
    log(f"GITHUB_REF={gh_ref}")
    log(f"GITHUB_EVENT_NAME={gh_event}")
    mf = MatrixFilter(gh_ref, gh_event)

    result_includes = [to_matrix_entry(c) for c in COMBOS if mf.should_run(c)]
    matrix = {"include": result_includes}

    log("resulting matrix:")
    pprint.pprint(matrix)

    outfile = pathlib.Path(os.environ["GITHUB_OUTPUT"])
    outfile.write_text(f"matrix={json.dumps(matrix)}\n")


if __name__ == "__main__":
    main()
