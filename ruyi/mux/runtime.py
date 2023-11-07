import os
import pathlib
import sys
from typing import List, NoReturn, Optional, Union

from rich import print

from .. import log


def mux_main(argv: List[str]) -> Union[int, NoReturn]:
    log.D(f"mux mode: argv = {argv}")

    # if no preference is set for the cwd, find the next command in PATH with
    # the same argv[0], and exec it
    next = find_next_in_path(os.path.basename(argv[0]))
    if next is None:
        log.F(f"cannot find a '[yellow]{argv[0]}[/yellow]' to exec")
        return 127

    new_argv = [next] + argv[1:]
    log.D(f"exec-ing [green]{next}[/green] with argv {new_argv}")
    return os.execv(next, new_argv)


# This is intended to resemble shutil.which, but knows to skip ruyi itself to
# avoid infinite looping.
def find_next_in_path(
    argv0: str, search_paths: Optional[List[str]] = None
) -> Optional[str]:
    from ..cli import _self_exe

    if search_paths is None:
        path_str = os.environ.get("PATH", os.defpath)
        if not path_str:
            return None
        search_paths = path_str.split(":")

    # this is mirroring shutil.which logic, but skips the PATHEXT handling for
    # now.
    seen = set()
    for dir in search_paths:
        normalized = os.path.normcase(dir)
        if normalized in seen:
            continue

        seen.add(normalized)
        p = os.path.join(dir, argv0)
        if is_executable(p) and not os.path.samefile(p, _self_exe):
            return p

    return None


def is_executable(p: Union[str, pathlib.Path]) -> bool:
    p = p if isinstance(p, pathlib.Path) else pathlib.Path(p)
    try:
        return os.access(p, os.F_OK | os.X_OK)
    except FileNotFoundError:
        return False
