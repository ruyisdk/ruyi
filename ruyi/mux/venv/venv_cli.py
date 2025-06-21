import argparse
import pathlib
from typing import TYPE_CHECKING

from ...cli.cmd import RootCommand

if TYPE_CHECKING:
    from ...config import GlobalConfig


class VenvCommand(
    RootCommand,
    cmd="venv",
    help="Generate a virtual environment adapted to the chosen toolchain and profile",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: argparse.ArgumentParser) -> None:
        p.add_argument("profile", type=str, help="Profile to use for the environment")
        p.add_argument("dest", type=str, help="Path to the new virtual environment")
        p.add_argument(
            "--name",
            "-n",
            type=str,
            default=None,
            help="Override the venv's name",
        )
        p.add_argument(
            "--toolchain",
            "-t",
            type=str,
            action="append",
            help="Specifier(s) (atoms) of the toolchain package(s) to use",
        )
        p.add_argument(
            "--emulator",
            "-e",
            type=str,
            help="Specifier (atom) of the emulator package to use",
        )
        p.add_argument(
            "--with-sysroot",
            action="store_true",
            dest="with_sysroot",
            default=True,
            help="Provision a fresh sysroot inside the new virtual environment (default)",
        )
        p.add_argument(
            "--without-sysroot",
            action="store_false",
            dest="with_sysroot",
            help="Do not include a sysroot inside the new virtual environment",
        )
        p.add_argument(
            "--sysroot-from",
            type=str,
            help="Specifier (atom) of the sysroot package to use, in favor of the toolchain-included one if applicable",
        )
        p.add_argument(
            "--extra-commands-from",
            type=str,
            action="append",
            help="Specifier(s) (atoms) of extra package(s) to add commands to the new virtual environment",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ...ruyipkg.host import get_native_host
        from .maker import do_make_venv

        profile_name: str = args.profile
        dest = pathlib.Path(args.dest)
        with_sysroot: bool = args.with_sysroot
        override_name: str | None = args.name
        tc_atoms_str: list[str] | None = args.toolchain
        emu_atom_str: str | None = args.emulator
        sysroot_atom_str: str | None = args.sysroot_from
        extra_cmd_atoms_str: list[str] | None = args.extra_commands_from
        host = str(get_native_host())

        return do_make_venv(
            cfg,
            host,
            profile_name,
            dest,
            with_sysroot,
            override_name,
            tc_atoms_str,
            emu_atom_str,
            sysroot_atom_str,
            extra_cmd_atoms_str,
        )
