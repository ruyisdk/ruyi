import os
import re
import shlex
from typing import List, NoReturn

from .. import log
from ..config import RuyiVenvConfig


def mux_main(argv: List[str]) -> int | NoReturn:
    basename = os.path.basename(argv[0])
    log.D(f"mux mode: argv = {argv}, basename = {basename}")

    vcfg = RuyiVenvConfig.load_from_venv()
    if vcfg is None:
        log.F("the Ruyi toolchain mux is not configured")
        log.I("check out `ruyi venv` for making a virtual environment")
        return 1

    binpath = os.path.join(vcfg.toolchain_bindir, basename)

    log.D(f"binary to exec: {binpath}")

    common_argv_to_insert: list[str] | None = None
    if is_proxying_to_cc(basename):
        log.D(f"{basename} is considered a CC")
        common_argv_to_insert = shlex.split(vcfg.profile_common_flags)
        log.D(f"parsed profile flags: {common_argv_to_insert}")

    new_argv = [binpath]
    if common_argv_to_insert is not None:
        new_argv.extend(common_argv_to_insert)
    if len(argv) > 1:
        new_argv.extend(argv[1:])

    log.D(f"exec-ing with argv {new_argv}")
    return os.execv(binpath, new_argv)


# TODO: dedup with venv provision logic (into a command name parser)
CC_ARGV0_RE = re.compile(
    r"(?:^|-)(?:g?cc|c\+\+|g\+\+|cpp|clang|clang\+\+)(?:-[0-9.]+)?$"
)


def is_proxying_to_cc(argv0: str) -> bool:
    return CC_ARGV0_RE.search(argv0) is not None
