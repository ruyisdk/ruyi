import argparse
from os import PathLike
import pathlib
from typing import Any

from ... import log
from ...config import GlobalConfig
from ...ruyipkg.atom import Atom
from ...ruyipkg.host import get_native_host
from ...ruyipkg.repo import MetadataRepo
from .provision import render_template_str, VenvMaker


def cli_venv(args: argparse.Namespace) -> int:
    profile_name: str = args.profile
    dest = pathlib.Path(args.dest)
    with_sysroot: bool = args.with_sysroot
    override_name: str | None = args.name
    tc_atom_str: str | None = args.toolchain
    emu_atom_str: str | None = args.emulator
    sysroot_atom_str: str | None = args.sysroot_from
    host = get_native_host()

    # TODO: support omitting this if user only has one toolchain installed
    # this should come after implementation of local state cache
    if tc_atom_str is None:
        log.F(
            "You have to explicitly specify a toolchain atom for now, e.g. [yellow]`-t gnu-plct`[/yellow]"
        )
        return 1

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)

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

    if not tc_pm.toolchain_metadata.satisfies_flavor_set(profile.need_flavor):
        log.F(
            f"the package [yellow]{tc_atom_str}[/yellow] does not support all necessary features for the profile [yellow]{profile_name}[/yellow]"
        )
        log.I(
            f"feature(s) needed by profile:   {log.humanize_list(profile.need_flavor, item_color='cyan')}"
        )
        log.I(
            f"feature(s) provided by package: {log.humanize_list(tc_pm.toolchain_metadata.flavors, item_color='yellow')}"
        )
        return 1

    target_tuple = tc_pm.toolchain_metadata.target

    toolchain_root = config.lookup_binary_install_dir(
        host,
        tc_pm.name_for_installation,
    )
    if toolchain_root is None:
        log.F("cannot find the installed directory for the toolchain")
        return 1

    gcc_install_dir: PathLike[Any] | None = None
    tc_sysroot_dir: PathLike[Any] | None = None
    if with_sysroot:
        tc_sysroot_relpath = tc_pm.toolchain_metadata.included_sysroot
        if tc_sysroot_relpath is not None:
            tc_sysroot_dir = pathlib.Path(toolchain_root) / tc_sysroot_relpath
        else:
            if sysroot_atom_str is None:
                log.F(
                    f"sysroot is requested but the toolchain package does not include one, and [yellow]--sysroot-from[/yellow] is not given"
                )
                return 1

            # try extracting from the sysroot package
            # for now only GCC toolchain packages can provide sysroots, so this is
            # okay
            gcc_pkg_atom = Atom.parse(sysroot_atom_str)
            gcc_pkg_pm = gcc_pkg_atom.match_in_repo(mr, config.include_prereleases)
            if gcc_pkg_pm is None:
                log.F(
                    f"cannot match a toolchain package with [yellow]{sysroot_atom_str}[/yellow]"
                )
                return 1

            if gcc_pkg_pm.toolchain_metadata is None:
                log.F(
                    f"the package [yellow]{sysroot_atom_str}[/yellow] is not a toolchain"
                )
                return 1

            gcc_pkg_root = config.lookup_binary_install_dir(
                host,
                gcc_pkg_pm.name_for_installation,
            )
            if gcc_pkg_root is None:
                log.F("cannot find the installed directory for the sysroot package")
                return 1

            tc_sysroot_relpath = gcc_pkg_pm.toolchain_metadata.included_sysroot
            if tc_sysroot_relpath is None:
                log.F(
                    f"sysroot is requested but the package [yellow]{sysroot_atom_str}[/yellow] does not contain one"
                )
                return 1

            tc_sysroot_dir = pathlib.Path(gcc_pkg_root) / tc_sysroot_relpath

            # also figure the GCC include/libs path out for Clang to be able to
            # locate them
            gcc_install_dir = find_gcc_install_dir(
                gcc_pkg_root,
                # we should use the GCC-providing package's target tuple as that's
                # not guaranteed to be the same as llvm's
                gcc_pkg_pm.toolchain_metadata.target,
            )

            # for now, require this directory to be present (or clang would barely work)
            if gcc_install_dir is None:
                log.F(
                    "cannot find a GCC include & lib directory in the sysroot package"
                )
                return 1

    target_arch = tc_pm.toolchain_metadata.target_arch

    # Now handle the emulator.
    emu_progs = None
    emu_root: PathLike[Any] | None = None
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

        for prog in emu_progs:
            if not profile.check_emulator_flavor(
                prog.flavor, emu_pm.emulator_metadata.flavors
            ):
                log.F(
                    f"the package [yellow]{emu_atom_str}[/yellow] does not support all necessary features for the profile [yellow]{profile_name}[/yellow]"
                )
                log.I(
                    f"feature(s) needed by profile:   {log.humanize_list(profile.get_needed_emulator_pkg_flavors(prog.flavor), item_color='cyan')}"
                )
                log.I(
                    f"feature(s) provided by package: {log.humanize_list(emu_pm.emulator_metadata.flavors or [], item_color='yellow')}"
                )
                return 1

        emu_root = config.lookup_binary_install_dir(
            host,
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
        target_tuple,
        # assume clang is preferred if package contains clang
        # this is mostly true given most packages don't contain both
        "clang" if tc_pm.toolchain_metadata.has_clang else "gcc",
        # same for binutils provider flavor
        "llvm" if tc_pm.toolchain_metadata.has_llvm else "binutils",
        dest.resolve(),
        tc_sysroot_dir,
        gcc_install_dir,
        emu_progs,
        emu_root,
        override_name,
    )
    maker.provision()

    log.I(
        render_template_str(
            "prompt.venv-created.txt",
            {
                "sysroot": maker.sysroot_destdir,
            },
        )
    )

    return 0


def find_gcc_install_dir(
    install_root: PathLike[Any],
    target_tuple: str,
) -> PathLike[Any] | None:
    # check $PREFIX/lib/gcc/$TARGET/*
    search_root = pathlib.Path(install_root) / "lib" / "gcc" / target_tuple
    try:
        for p in search_root.iterdir():
            # only want the first one (should be the only one)
            return p
    except FileNotFoundError:
        pass

    # nothing?
    return None
