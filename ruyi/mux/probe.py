import argparse
import pathlib
from typing import List, Optional, Set

from rich import print

from ruyi import is_debug


CC_FLAVOR_GCC = "gcc"
CC_FLAVOR_CLANG = "clang"

LD_FLAVOR_BFD = "ld.bfd"
LD_FLAVOR_LLD = "ld.lld"
LD_FLAVOR_MOLD = "ld.mold"

LIBC_FLAVOR_NONE = "none"
LIBC_FLAVOR_GLIBC = "glibc"
LIBC_FLAVOR_MUSL = "musl"


class ToolchainCharacteristics:
    def __init__(
        self,
        sysroot: Optional[str] = None,
        host_tuple: str = "",
        target_tuple: str = "",
        flags: Optional[Set[str]] = None,
    ) -> None:
        self.sysroot = sysroot or ""
        self.host_tuple = host_tuple
        self.target_tuple = target_tuple
        self.flags = flags or set()


# Substrings of toolchain-related command names that have relatively low chance
# of false-positives when doing naïve matching.
WELL_KNOWN_COMMAND_GLOBS = [
    "*-clang",
    "*-clang++",
    "*-gcc",
    "*-g++",
]


def probe_by_bindir(path: str) -> List[ToolchainCharacteristics]:
    p = pathlib.Path(path)
    candidates: List[pathlib.Path] = []
    for pat in WELL_KNOWN_COMMAND_GLOBS:
        for match in p.glob(pat):
            candidates.append(match)

    if is_debug():
        print(f"[cyan]debug:[/cyan] {len(candidates)} candidate(s) found")
        for p in candidates:
            print(f"  {p}")

    return []


def cli_probe(args: argparse.Namespace) -> int:
    bindir = args.bindir
    probe_by_bindir(bindir)
    return 0
