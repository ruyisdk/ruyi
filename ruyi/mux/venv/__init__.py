import argparse
import pathlib
import platform

from ... import log
from ...config import GlobalConfig
from ...ruyipkg.atom import Atom
from ...ruyipkg.repo import MetadataRepo
from .provision import VenvMaker


def cli_venv(args: argparse.Namespace) -> int:
    profile_name: str = args.profile
    dest = pathlib.Path(args.dest)
    with_sysroot: bool = args.with_sysroot
    override_name: str | None = args.name
    tc_atom_str: str | None = args.toolchain

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
    # TODO: check the local cache to get rid of the hardcoded True
    tc_pm = tc_atom.match_in_repo(mr, True)
    if tc_pm is None:
        log.F(f"cannot match a toolchain package with [yellow]{tc_atom_str}[/yellow]")
        return 1

    if tc_pm.toolchain_metadata is None:
        log.F(f"the package is not a toolchain")
        return 1

    toolchain_root = config.global_binary_install_root(
        platform.machine(),  # TODO
        tc_pm.name_for_installation,
    )

    tc_sysroot_dir: pathlib.Path | None = None
    if with_sysroot:
        tc_sysroot_relpath = tc_pm.toolchain_metadata.included_sysroot
        if tc_sysroot_relpath is None:
            log.F(
                f"sysroot is requested but the toolchain package does not include one"
            )
            return 1
        tc_sysroot_dir = pathlib.Path(toolchain_root) / tc_sysroot_relpath

    if override_name is not None:
        log.I(
            f"Creating a Ruyi virtual environment [cyan]'{override_name}'[/cyan] at [green]{dest}[/green]..."
        )
    else:
        log.I(f"Creating a Ruyi virtual environment at [green]{dest}[/green]...")

    maker = VenvMaker(
        profile,
        toolchain_root,
        dest.resolve(),
        tc_sysroot_dir,
        override_name,
    )
    maker.provision()

    log.I(
        """\
The virtual environment is now created.

You may activate it by sourcing the appropriate activation script in the
[green]bin[/green] directory, and deactivate by invoking `ruyi-deactivate`.
"""
    )

    return 0
