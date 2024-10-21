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

    direct_symlink_target = resolve_direct_symlink_target(argv[0], vcfg)
    if direct_symlink_target is not None:
        log.D(
            f"detected direct symlink target: {direct_symlink_target}, overriding basename"
        )
        basename = direct_symlink_target

    if basename == "ruyi-qemu":
        return mux_qemu_main(argv, vcfg)

    # match the basename with one of the configured target tuples
    target_tuple: str | None = None
    binpath: str | None = None
    toolchain_sysroot: str | None = None
    gcc_install_dir: str | None = None

    # prefer v1 cached info which is lossless
    if md := vcfg.resolve_cmd_metadata_with_cache(basename):
        target_tuple = md["target_tuple"]
        binpath = md["dest"]
        tgt_data = vcfg.targets[target_tuple]
        toolchain_sysroot = tgt_data.get("toolchain_sysroot")
        gcc_install_dir = tgt_data.get("gcc_install_dir")
    else:
        toolchain_bindir: str | None = None
        for tgt_tuple, tgt_data in vcfg.targets.items():
            if not basename.startswith(f"{tgt_tuple}-"):
                continue

            log.D(f"matched target '{tgt_tuple}', data {tgt_data}")
            target_tuple = tgt_tuple
            toolchain_bindir = tgt_data["toolchain_bindir"]
            toolchain_sysroot = tgt_data.get("toolchain_sysroot")
            gcc_install_dir = tgt_data.get("gcc_install_dir")
            break

        if toolchain_bindir is None:
            # should not happen
            log.F(
                f"internal error: no bindir configured for target [yellow]{target_tuple}[/]"
            )
            return 1

        binpath = os.path.join(toolchain_bindir, basename)

    if target_tuple is None:
        log.F(f"no configured target found for command [yellow]{basename}[/]")
        return 1

    log.D(f"binary to exec: {binpath}")

    argv_to_insert: list[str] | None = None
    if is_proxying_to_cc(basename):
        log.D(f"{basename} is considered a CC")

        argv_to_insert = []

        if is_proxying_to_clang(basename):
            log.D(f"adding target for clang: {target_tuple}")
            argv_to_insert.append(f"--target={target_tuple}")
            if gcc_install_dir is not None:
                log.D(f"informing clang of GCC install dir: {gcc_install_dir}")
                argv_to_insert.append(f"--gcc-install-dir={gcc_install_dir}")

        argv_to_insert.extend(shlex.split(vcfg.profile_common_flags))
        log.D(f"parsed profile flags: {argv_to_insert}")

        if toolchain_sysroot is not None:
            log.D(f"adding sysroot: {toolchain_sysroot}")
            argv_to_insert.extend(("--sysroot", toolchain_sysroot))

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


def resolve_direct_symlink_target(argv0: str, vcfg: RuyiVenvConfig) -> str | None:
    direct_symlink_target = resolve_argv0_symlink(argv0, vcfg)
    if direct_symlink_target is not None and os.path.sep in direct_symlink_target:
        # we're not designed to handle such indirections
        return None
    return direct_symlink_target


def resolve_argv0_symlink(argv0: str, vcfg: RuyiVenvConfig) -> str | None:
    if os.path.sep in argv0:
        # argv[0] contains path information that we can just use
        try:
            return os.readlink(argv0)
        except OSError:
            # argv[0] is not a symlink
            return None

    # argv[0] is bare command name, in which case we expect venv root to
    # be available, so we can just check f'{venv_root}/bin/{argv[0]}'.
    # we're guaranteed a venv_root because of the vcfg init logic.
    try:
        return os.readlink(vcfg.venv_root / "bin" / argv0)
    except OSError:
        return None


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
    venv_root = vcfg.venv_root
    venv_bindir = venv_root / "bin"
    venv_bindir = venv_bindir.resolve()

    orig_path = os.environ.get("PATH", "")
    for p in orig_path.split(os.pathsep):
        try:
            if os.path.samefile(p, venv_bindir):
                # TODO: what if our bindir actually comes after the system ones?
                return
        except FileNotFoundError:
            # maybe the PATH entry is stale
            continue

    # we're not in PATH, so prepend the bindir to PATH
    os.environ["PATH"] = f"{venv_bindir}:{orig_path}" if orig_path else str(venv_bindir)
