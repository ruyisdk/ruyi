import argparse
import os
import sys
from typing import List

from rich import print

from ruyi import is_debug, set_debug
from .mux import mux_main
from ..mux.probe import cli_probe

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


def init_argparse() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog=RUYI_ENTRYPOINT_NAME,
        description="RuyiSDK Package Manager",
    )
    sp = root.add_subparsers(required=True)

    tc = sp.add_parser("toolchain", help="Query and manage toolchains")
    tcsp = tc.add_subparsers(required=True)
    tc_probe = tcsp.add_parser(
        "probe", help="Probe a directory for manageable toolchains"
    )
    tc_probe.set_defaults(func=cli_probe)
    tc_probe.add_argument(
        "bindir", help="Path to the directory containing toolchain commands"
    )

    return root


def main(argv: List[str]) -> int:
    init_debug_status()

    if not argv:
        print("[bold red]fatal error:[/bold red] no argv?", file=sys.stderr)
        return 1

    if is_debug():
        print(f"[cyan]debug:[/cyan] argv[0] = {argv[0]}")

    if not is_called_as_ruyi(argv[0]):
        return mux_main(argv)

    p = init_argparse()
    args = p.parse_args(argv[1:])
    if is_debug():
        print(f"[cyan]debug:[/cyan] args={args}")

    try:
        return args.func(args)
    except Exception as e:
        # print(f"[bold red]fatal error:[/bold red] no command specified {e}")
        # return 1
        raise

    return 0
