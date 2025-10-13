import argparse
import pathlib
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand
from .cli_completion import package_completer_builder
from .host import get_native_host

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class ExtractCommand(
    RootCommand,
    cmd="extract",
    help="Fetch package(s) then extract to current directory",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package(s) to extract",
        )
        if gc.is_cli_autocomplete:
            a.completer = package_completer_builder(gc)

        p.add_argument(
            "-d",
            "--dest-dir",
            type=str,
            metavar="DESTDIR",
            default=".",
            help="Destination directory to extract to (default: current directory)",
        )
        p.add_argument(
            "--extract-without-subdir",
            action="store_true",
            help="Extract files directly into DESTDIR instead of package-named subdirectories",
        )
        p.add_argument(
            "-f",
            "--fetch-only",
            action="store_true",
            help="Fetch distribution files only without installing",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .host import canonicalize_host_str
        from .install import do_extract_atoms

        atom_strs: set[str] = set(args.atom)
        dest_dir_arg: str = args.dest_dir
        extract_without_subdir: bool = args.extract_without_subdir
        host: str = args.host
        fetch_only: bool = args.fetch_only

        dest_dir = None if dest_dir_arg == "." else pathlib.Path(dest_dir_arg)

        return do_extract_atoms(
            cfg,
            cfg.repo,
            atom_strs,
            canonicalized_host=canonicalize_host_str(host),
            dest_dir=dest_dir,
            extract_without_subdir=extract_without_subdir,
            fetch_only=fetch_only,
        )


class InstallCommand(
    RootCommand,
    cmd="install",
    aliases=["i"],
    help="Install package from configured repository",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package to install",
        )
        if gc.is_cli_autocomplete:
            a.completer = package_completer_builder(gc)

        p.add_argument(
            "-f",
            "--fetch-only",
            action="store_true",
            help="Fetch distribution files only without installing",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )
        p.add_argument(
            "--reinstall",
            action="store_true",
            help="Force re-installation of already installed packages",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .host import canonicalize_host_str
        from .install import do_install_atoms

        host: str = args.host
        atom_strs: set[str] = set(args.atom)
        fetch_only: bool = args.fetch_only
        reinstall: bool = args.reinstall

        return do_install_atoms(
            cfg,
            cfg.repo,
            atom_strs,
            canonicalized_host=canonicalize_host_str(host),
            fetch_only=fetch_only,
            reinstall=reinstall,
        )


class UninstallCommand(
    RootCommand,
    cmd="uninstall",
    aliases=["remove", "rm"],
    help="Uninstall installed packages",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package to uninstall",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )
        p.add_argument(
            "-y",
            "--yes",
            action="store_true",
            dest="assume_yes",
            help="Assume yes to all prompts",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .host import canonicalize_host_str
        from .install import do_uninstall_atoms

        host: str = args.host
        atom_strs: set[str] = set(args.atom)
        assume_yes: bool = args.assume_yes

        return do_uninstall_atoms(
            cfg,
            cfg.repo,
            atom_strs,
            canonicalized_host=canonicalize_host_str(host),
            assume_yes=assume_yes,
        )
