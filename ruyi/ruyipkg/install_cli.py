import argparse

from ..cli.cmd import RootCommand
from ..config import GlobalConfig
from .host import canonicalize_host_str, get_native_host
from .install import do_extract_atoms, do_install_atoms, do_uninstall_atoms


class ExtractCommand(
    RootCommand,
    cmd="extract",
    help="Fetch package(s) then extract to current directory",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package(s) to extract",
        )
        p.add_argument(
            "--host",
            type=str,
            default=get_native_host(),
            help="Override the host architecture (normally not needed)",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        host: str = args.host
        atom_strs: set[str] = set(args.atom)

        return do_extract_atoms(
            cfg,
            cfg.repo,
            atom_strs,
            canonicalized_host=canonicalize_host_str(host),
        )


class InstallCommand(
    RootCommand,
    cmd="install",
    aliases=["i"],
    help="Install package from configured repository",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "atom",
            type=str,
            nargs="+",
            help="Specifier (atom) of the package to install",
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
        p.add_argument(
            "--reinstall",
            action="store_true",
            help="Force re-installation of already installed packages",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        host = args.host
        atom_strs: set[str] = set(args.atom)
        fetch_only = args.fetch_only
        reinstall = args.reinstall

        mr = cfg.repo

        return do_install_atoms(
            cfg,
            mr,
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
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
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
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
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
