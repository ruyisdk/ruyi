import os
import re
import shlex
from typing import List, NoReturn

from .. import log
from ..config import RuyiVenvConfig


def mux_main(argv: List[str]) -> int | NoReturn:
    basename = os.path.basename(argv[0])
    log.D(f"mux mode: argv = {argv}, basename = {basename}")

    direct_symlink_target: str | None = None
    try:
        direct_symlink_target = os.readlink(argv[0])
    except OSError:
        # argv[0] is not a symlink
        pass

    if direct_symlink_target is not None and os.path.sep in direct_symlink_target:
        # we're not designed to handle such indirections
        direct_symlink_target = None

    if direct_symlink_target is not None:
        log.D(
            f"detected indirect symlink target: {direct_symlink_target}, overriding basename"
        )
        basename = direct_symlink_target

    vcfg = RuyiVenvConfig.load_from_venv()
    if vcfg is None:
        log.F("the Ruyi toolchain mux is not configured")
        log.I("check out `ruyi venv` for making a virtual environment")
        return 1

    if basename == "ruyi-qemu":
        return mux_qemu_main(argv, vcfg)

    binpath = os.path.join(vcfg.toolchain_bindir, basename)

    log.D(f"binary to exec: {binpath}")

    argv_to_insert: list[str] | None = None
    if is_proxying_to_cc(basename):
        log.D(f"{basename} is considered a CC")

        argv_to_insert = []

        if is_proxying_to_clang(basename):
            log.D(f"adding target for clang: {vcfg.target_tuple}")
            argv_to_insert.append(f"--target={vcfg.target_tuple}")

        argv_to_insert.extend(shlex.split(vcfg.profile_common_flags))
        log.D(f"parsed profile flags: {argv_to_insert}")

        if vcfg.sysroot is not None:
            log.D(f"adding sysroot: {vcfg.sysroot}")
            argv_to_insert.extend(("--sysroot", vcfg.sysroot))

    new_argv = [binpath]
    if argv_to_insert:
        new_argv.extend(argv_to_insert)
    if len(argv) > 1:
        new_argv.extend(argv[1:])

    ensure_venv_in_path(vcfg)

    log.D(f"exec-ing with argv {new_argv}")
    return os.execv(binpath, new_argv)


# TODO: dedup with venv provision logic (into a command name parser)
CC_ARGV0_RE = re.compile(
    r"(?:^|-)(?:g?cc|c\+\+|g\+\+|cpp|clang|clang\+\+|clang-cl|clang-cpp)(?:-[0-9.]+)?$"
)


def is_proxying_to_cc(argv0: str) -> bool:
    return CC_ARGV0_RE.search(argv0) is not None


def is_proxying_to_clang(basename: str) -> bool:
    return "clang" in basename


def mux_qemu_main(argv: List[str], vcfg: RuyiVenvConfig) -> int | NoReturn:
    binpath = vcfg.qemu_bin
    if binpath is None:
        log.F("this virtual environment has no QEMU-like emulator configured")
        return 1

    if vcfg.profile_emu_env is not None:
        log.D(f"seeding QEMU environment with {vcfg.profile_emu_env}")
        for k, v in vcfg.profile_emu_env.items():
            os.environ[k] = v

    log.D(f"QEMU binary to exec: {binpath}")

    new_argv = [binpath]
    if len(argv) > 1:
        new_argv.extend(argv[1:])

    log.D(f"exec-ing with argv {new_argv}")
    return os.execv(binpath, new_argv)


def ensure_venv_in_path(vcfg: RuyiVenvConfig) -> None:
    venv_root = vcfg.venv_root()
    assert venv_root is not None
    venv_bindir = venv_root / "bin"
    venv_bindir = venv_bindir.resolve()

    orig_path = os.environ.get("PATH", "")
    for p in orig_path.split(os.pathsep):
        if os.path.samefile(p, venv_bindir):
            # TODO: what if our bindir actually comes after the system ones?
            return

    # we're not in PATH, so prepend the bindir to PATH
    os.environ["PATH"] = f"{venv_bindir}:{orig_path}" if orig_path else str(venv_bindir)
