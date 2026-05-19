import argparse
import pathlib
from typing import TYPE_CHECKING

from ...cli.cmd import RootCommand
from ...i18n import _

if TYPE_CHECKING:
    from ...cli.completion import ArgumentParser
    from ...config import GlobalConfig


class VenvCommand(
    RootCommand,
    cmd="venv",
    help=_("Generate a virtual environment adapted to the chosen toolchain and profile"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.formatter_class = argparse.RawDescriptionHelpFormatter
        p.epilog = _(
            "Sysroot provisioning:\n"
            "  By default, Ruyi uses the sysroot bundled with the selected toolchain if one is available.\n"
            "  Use --copy-sysroot-from-pkg to copy the sysroot from another installed toolchain package.\n"
            "  Use --copy-sysroot-from-dir only for a complete sysroot directory readable by the current user; it performs a faithful full-tree copy.\n"
            "  Use --symlink-sysroot-from-dir to point the virtual environment at an existing sysroot directory without copying it.\n"
            "  Use --project-sysroot-from-rootfs for distro rootfs or chroot trees: Ruyi copies common cross-build directories such as include, lib*, usr/include, usr/lib*, usr/share, bin, and sbin, and skips unreadable or unsupported files.\n"
            "  Ruyi never elevates privileges when creating virtual environments. If a rootfs contains private system files such as /etc/shadow, prepare a readable sysroot yourself or use projection mode."
        )
        p.add_argument("profile", type=str, help=_("Profile to use for the environment"),
                       )
        p.add_argument("dest", type=str, help=_("Path to the new virtual environment"),
                       )
        p.add_argument(
            "--name",
            "-n",
            type=str,
            default=None,
            help=_("Override the venv's name"),
        )
        p.add_argument(
            "--toolchain",
            "-t",
            type=str,
            action="append",
            help=_("Specifier(s) (atoms) of the toolchain package(s) to use"),
        )
        p.add_argument(
            "--emulator",
            "-e",
            type=str,
            help=_("Specifier (atom) of the emulator package to use"),
        )
        p.add_argument(
            "--with-sysroot",
            action="store_true",
            dest="with_sysroot",
            default=True,
            help=_("Provision a fresh sysroot inside the new virtual environment (default)"),
        )
        p.add_argument(
            "--without-sysroot",
            action="store_false",
            dest="with_sysroot",
            help=_("Do not include a sysroot inside the new virtual environment"),
        )
        p.add_argument(
            "--copy-sysroot-from-pkg",
            "--sysroot-from",
            type=str,
            dest="copy_sysroot_from_pkg",
            help=_("Specifier (atom) of the sysroot package to use, in favor of the toolchain-included one if applicable"),
        )
        p.add_argument(
            "--copy-sysroot-from-dir",
            type=str,
            help=_("Copy the sysroot from the given directory into the virtual environment"),
        )
        p.add_argument(
            "--symlink-sysroot-from-dir",
            type=str,
            help=_("Symlink the virtual environment's sysroot to the given existing directory"),
        )
        p.add_argument(
            "--project-sysroot-from-rootfs",
            type=str,
            help=_("Project a build sysroot from the given distro rootfs directory"),
        )
        p.add_argument(
            "--extra-commands-from",
            type=str,
            action="append",
            help=_("Specifier(s) (atoms) of extra package(s) to add commands to the new virtual environment"),
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ...ruyipkg.host import get_native_host
        from .maker import do_make_venv

        # validate sysroot source options: at most one source may be specified
        sysroot_sources = sum([
            args.copy_sysroot_from_pkg is not None,
            args.copy_sysroot_from_dir is not None,
            args.symlink_sysroot_from_dir is not None,
            args.project_sysroot_from_rootfs is not None,
        ])
        if sysroot_sources > 1:
            cfg.logger.F(
                _("at most one of --copy-sysroot-from-pkg, --copy-sysroot-from-dir, --symlink-sysroot-from-dir, and --project-sysroot-from-rootfs may be specified")
            )
            return 1

        if not args.with_sysroot and sysroot_sources > 0:
            cfg.logger.F(
                _("--without-sysroot cannot be combined with a sysroot source option")
            )
            return 1

        profile_name: str = args.profile
        dest = pathlib.Path(args.dest)
        with_sysroot: bool = args.with_sysroot
        override_name: str | None = args.name
        tc_atoms_str: list[str] | None = args.toolchain
        emu_atom_str: str | None = args.emulator
        sysroot_atom_str: str | None = args.copy_sysroot_from_pkg
        copy_sysroot_dir_str: str | None = args.copy_sysroot_from_dir
        symlink_sysroot_dir_str: str | None = args.symlink_sysroot_from_dir
        project_sysroot_dir_str: str | None = args.project_sysroot_from_rootfs
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
            copy_sysroot_dir_str,
            symlink_sysroot_dir_str,
            project_sysroot_dir_str,
            extra_cmd_atoms_str,
        )
