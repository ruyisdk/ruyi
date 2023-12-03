import argparse
from os import PathLike
import pathlib
import platform

from ... import log
from ...config import GlobalConfig
from ...ruyipkg.atom import Atom
from ...ruyipkg.repo import MetadataRepo
from .provision import render_template_str, VenvMaker


def cli_venv(args: argparse.Namespace) -> int:
    profile_name: str = args.profile
    dest = pathlib.Path(args.dest)
    with_sysroot: bool = args.with_sysroot
    override_name: str | None = args.name
    tc_atom_str: str | None = args.toolchain
    emu_atom_str: str | None = args.emulator

    # TODO: support omitting this if user only has one toolchain installed
    # this should come after implementation of local state cache
    if tc_atom_str is None:
        log.F(
            "You have to explicitly specify a toolchain atom for now, e.g. [yellow]`-t gnu-plct`[/yellow]"
        )
        return 1

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(),
        config.get_repo_url(),
        config.get_repo_branch(),
    )

    profile = mr.get_profile(profile_name)
    if profile is None:
        log.F(f"profile '{profile_name}' not found")
        return 1

    tc_atom = Atom.parse(tc_atom_str)
    tc_pm = tc_atom.match_in_repo(mr, config.include_prereleases)
    if tc_pm is None:
        log.F(f"cannot match a toolchain package with [yellow]{tc_atom_str}[/yellow]")
        return 1

    if tc_pm.toolchain_metadata is None:
        log.F(f"the package [yellow]{tc_atom_str}[/yellow] is not a toolchain")
        return 1

    toolchain_root = config.lookup_binary_install_dir(
        platform.machine(),  # TODO
        tc_pm.name_for_installation,
    )
    if toolchain_root is None:
        log.F("cannot find the installed directory for the toolchain")
        return 1

    tc_sysroot_dir: pathlib.Path | None = None
    if with_sysroot:
        tc_sysroot_relpath = tc_pm.toolchain_metadata.included_sysroot
        if tc_sysroot_relpath is None:
            log.F(
                f"sysroot is requested but the toolchain package does not include one"
            )
            return 1
        tc_sysroot_dir = pathlib.Path(toolchain_root) / tc_sysroot_relpath

    target_arch = tc_pm.toolchain_metadata.target_arch

    # Now handle the emulator.
    emu_progs = None
    emu_root: PathLike | None = None
    if emu_atom_str:
        emu_atom = Atom.parse(emu_atom_str)
        emu_pm = emu_atom.match_in_repo(mr, config.include_prereleases)
        if emu_pm is None:
            log.F(
                f"cannot match an emulator package with [yellow]{emu_atom_str}[/yellow]"
            )
            return 1

        if emu_pm.emulator_metadata is None:
            log.F(f"the package [yellow]{emu_atom_str}[/yellow] is not an emulator")
            return 1

        emu_progs = list(emu_pm.emulator_metadata.list_for_arch(target_arch))
        if not emu_progs:
            log.F(
                f"the emulator package [yellow]{emu_atom_str}[/yellow] does not support the target architecture [yellow]{target_arch}[/yellow]"
            )
            return 1

        emu_root = config.lookup_binary_install_dir(
            platform.machine(),  # TODO
            emu_pm.name_for_installation,
        )
        if emu_root is None:
            log.F("cannot find the installed directory for the emulator")
            return 1

    if override_name is not None:
        log.I(
            f"Creating a Ruyi virtual environment [cyan]'{override_name}'[/cyan] at [green]{dest}[/green]..."
        )
    else:
        log.I(f"Creating a Ruyi virtual environment at [green]{dest}[/green]...")

    maker = VenvMaker(
        profile,
        toolchain_root,
        tc_pm.toolchain_metadata.target,
        # assume clang is preferred if package contains clang
        # this is mostly true given most packages don't contain both
        "clang" if tc_pm.toolchain_metadata.has_clang else "gcc",
        # same for binutils provider flavor
        "llvm" if tc_pm.toolchain_metadata.has_llvm else "binutils",
        dest.resolve(),
        tc_sysroot_dir,
        emu_progs,
        emu_root,
        override_name,
    )
    maker.provision()

    log.I(
        render_template_str(
            "prompt.venv-created.txt",
            {
                "sysroot": dest.resolve() / "sysroot",
            },
        )
    )

    return 0
