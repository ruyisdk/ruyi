import argparse
import os
import sys
from typing import List

from rich import print

from ruyi import is_debug, set_debug
from .mux import mux_main

RUYI_ENTRYPOINT_NAME = "ruyi"


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0) in {RUYI_ENTRYPOINT_NAME, "__main__.py"}


_self_exe: str = ""


def record_self_exe(x: str) -> None:
    global _self_exe
    _self_exe = x


def init_debug_status() -> None:
    debug_env = os.environ.get("RUYI_DEBUG", "")
    set_debug(debug_env.lower() in {"1", "true", "x", "y", "yes"})


def main(argv: List[str]) -> int:
    init_debug_status()

    if not argv:
        print("[bold red]fatal error:[/bold red] no argv?", file=sys.stderr)
        return 1

    if is_debug():
        print(f"[cyan]debug:[/cyan] argv[0] = {argv[0]}")

    if not is_called_as_ruyi(argv[0]):
        return mux_main(argv)

    p = argparse.ArgumentParser(
        prog=RUYI_ENTRYPOINT_NAME,
        description="RuyiSDK Package Manager",
    )
    args = p.parse_args(argv[1:])
    print(args)

    return 0
