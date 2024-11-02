import argparse
import atexit
import os
import sys
from typing import Callable, IO, List, Protocol

from ..config import GlobalConfig
from ..version import RUYI_SEMVER

# Should be all-lower for is_called_as_ruyi to work
RUYI_ENTRYPOINT_NAME = "ruyi"

ALLOWED_RUYI_ENTRYPOINT_NAMES = (
    RUYI_ENTRYPOINT_NAME,
    f"{RUYI_ENTRYPOINT_NAME}.exe",
    f"{RUYI_ENTRYPOINT_NAME}.bin",  # Nuitka one-file program cache
    "__main__.py",
)


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0).lower() in ALLOWED_RUYI_ENTRYPOINT_NAMES


CLIEntrypoint = Callable[[GlobalConfig, argparse.Namespace], int]


class _PrintHelp(Protocol):
    def print_help(self, file: IO[str] | None = None) -> None: ...


def _wrap_help(x: _PrintHelp) -> CLIEntrypoint:
    def _wrapped_(gc: GlobalConfig, args: argparse.Namespace) -> int:
        x.print_help()
        return 0

    return _wrapped_


class BaseCommand:
    parsers: "list[type[BaseCommand]]" = []

    cmd: str | None
    _tele_key: str | None
    has_subcommands: bool
    is_subcommand_required: bool
    has_main: bool
    aliases: list[str]
    description: str | None
    prog: str | None
    help: str | None

    def __init_subclass__(
        cls,
        cmd: str | None,
        has_subcommands: bool = False,
        is_subcommand_required: bool = False,
        has_main: bool | None = None,
        aliases: list[str] | None = None,
        description: str | None = None,
        prog: str | None = None,
        help: str | None = None,
        **kwargs: object,
    ) -> None:
        cls.cmd = cmd

        if cmd is None:
            cls._tele_key = None
        else:
            parent_raw_tele_key = cls.mro()[1]._tele_key
            if parent_raw_tele_key is None:
                cls._tele_key = cmd
            else:
                cls._tele_key = f"{parent_raw_tele_key} {cmd}"

        cls.has_subcommands = has_subcommands
        cls.is_subcommand_required = is_subcommand_required
        cls.has_main = has_main if has_main is not None else not has_subcommands

        # argparse params
        cls.aliases = aliases or []
        cls.description = description
        cls.prog = prog
        cls.help = help

        cls.parsers.append(cls)

        super().__init_subclass__(**kwargs)

    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        """Configure arguments for this parser."""
        pass

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        """Entrypoint of this command."""
        raise NotImplementedError

    @classmethod
    def is_root(cls) -> bool:
        return cls.cmd is None

    @classmethod
    def _build_tele_key(cls) -> str:
        return "<bare>" if cls._tele_key is None else cls._tele_key

    @classmethod
    def build_argparse(cls) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(prog=cls.prog, description=cls.description)
        cls.configure_args(p)
        cls._populate_defaults(p)
        cls._maybe_build_subcommands(p)
        return p

    @classmethod
    def _maybe_build_subcommands(
        cls,
        p: argparse.ArgumentParser,
    ) -> None:
        if not cls.has_subcommands:
            return

        sp = p.add_subparsers(
            title="subcommands",
            required=cls.is_subcommand_required,
        )
        for subcmd_cls in cls.parsers:
            if subcmd_cls.mro()[1] is not cls:
                # do not recurse onto self or non-direct subclasses
                continue
            subcmd_cls._configure_subcommand(sp)

    @classmethod
    def _configure_subcommand(
        cls,
        sp: "argparse._SubParsersAction[argparse.ArgumentParser]",
    ) -> argparse.ArgumentParser:
        assert cls.cmd is not None
        p = sp.add_parser(
            cls.cmd,
            aliases=cls.aliases,
            help=cls.help,
        )
        cls.configure_args(p)
        cls._populate_defaults(p)
        cls._maybe_build_subcommands(p)
        return p

    @classmethod
    def _populate_defaults(cls, p: argparse.ArgumentParser) -> None:
        if cls.has_main:
            p.set_defaults(func=cls.main, tele_key=cls._build_tele_key())
        else:
            p.set_defaults(func=_wrap_help(p), tele_key=cls._build_tele_key())


class RootCommand(
    BaseCommand,
    cmd=None,
    has_subcommands=True,
    prog=RUYI_ENTRYPOINT_NAME,
    description=f"RuyiSDK Package Manager {RUYI_SEMVER}",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        from .version_cli import cli_version

        p.add_argument(
            "-V",
            "--version",
            action="store_const",
            dest="func",
            const=cli_version,
            help="Print version information",
        )
        p.add_argument(
            "--porcelain",
            action="store_true",
            help="Give the output in a machine-friendly format if applicable",
        )


class DeviceCommand(
    RootCommand,
    cmd="device",
    has_subcommands=True,
    help="Manage devices",
):
    pass


class DeviceProvisionCommand(
    DeviceCommand,
    cmd="provision",
    help="Interactively initialize a device for development",
):
    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..device.provision_cli import cli_device_provision

        return cli_device_provision(cfg, args)


class ExtractCommand(
    RootCommand,
    cmd="extract",
    help="Fetch package(s) then extract to current directory",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        from ..ruyipkg.host import get_native_host

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
        from ..ruyipkg.pkg_cli import cli_extract

        return cli_extract(cfg, args)


class InstallCommand(
    RootCommand,
    cmd="install",
    aliases=["i"],
    help="Install package from configured repository",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        from ..ruyipkg.host import get_native_host

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
        from ..ruyipkg.pkg_cli import cli_install

        return cli_install(cfg, args)


class ListCommand(
    RootCommand,
    cmd="list",
    has_subcommands=True,
    is_subcommand_required=False,
    has_main=True,
    help="List available packages in configured repository",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Also show details for every package",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.pkg_cli import cli_list

        return cli_list(cfg, args)


class ListProfilesCommand(
    ListCommand,
    cmd="profiles",
    help="List all available profiles",
):
    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.profile_cli import cli_list_profiles

        return cli_list_profiles(cfg, args)


class NewsCommand(
    RootCommand,
    cmd="news",
    has_subcommands=True,
    help="List and read news items from configured repository",
):
    pass


class NewsListCommand(
    NewsCommand,
    cmd="list",
    help="List news items",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--new",
            action="store_true",
            help="List unread news items only",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.news_cli import cli_news_list

        return cli_news_list(cfg, args)


class NewsReadCommand(
    NewsCommand,
    cmd="read",
    help="Read news items",
    description="Outputs news item(s) to the console and mark as already read. Defaults to reading all unread items if no item is specified.",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Do not output anything and only mark as read",
        )
        p.add_argument(
            "item",
            type=str,
            nargs="*",
            help="Ordinal or ID of the news item(s) to read",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.news_cli import cli_news_read

        return cli_news_read(cfg, args)


class UpdateCommand(
    RootCommand,
    cmd="update",
    help="Update RuyiSDK repo and packages",
):
    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.update_cli import cli_update

        return cli_update(cfg, args)


class VenvCommand(
    RootCommand,
    cmd="venv",
    help="Generate a virtual environment adapted to the chosen toolchain and profile",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
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

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..mux.venv.venv_cli import cli_venv

        return cli_venv(cfg, args)


# Repo admin commands
class AdminCommand(
    RootCommand,
    cmd="admin",
    has_subcommands=True,
    # https://github.com/python/cpython/issues/67037
    # help=argparse.SUPPRESS,
    help="(NOT FOR REGULAR USERS) Subcommands for managing Ruyi repos",
):
    pass


class AdminFormatManifestCommand(
    AdminCommand,
    cmd="format-manifest",
    help="Format the given package manifests into canonical TOML representation",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help="Path to the distfile(s) to generate manifest for",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.admin_cli import cli_admin_format_manifest

        return cli_admin_format_manifest(cfg, args)


class AdminManifestCommand(
    AdminCommand,
    cmd="manifest",
    help="Generate manifest for the distfiles given",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--format",
            "-f",
            type=str,
            choices=["json", "toml"],
            default="json",
            help="Format of manifest to generate",
        )
        p.add_argument(
            "--restrict",
            type=str,
            default="",
            help="the 'restrict' field to use for all mentioned distfiles, separated with comma",
        )
        p.add_argument(
            "file",
            type=str,
            nargs="+",
            help="Path to the distfile(s) to generate manifest for",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from ..ruyipkg.admin_cli import cli_admin_manifest

        return cli_admin_manifest(cfg, args)


# Self-management commands
class SelfCommand(
    RootCommand,
    cmd="self",
    has_subcommands=True,
    help="Manage this Ruyi installation",
):
    pass


class SelfCleanCommand(
    SelfCommand,
    cmd="clean",
    help="Remove various Ruyi-managed data to reclaim storage",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Do not print out the actions being performed",
        )
        p.add_argument(
            "--all",
            action="store_true",
            help="Remove all covered data",
        )
        p.add_argument(
            "--distfiles",
            action="store_true",
            help="Remove all downloaded distfiles if any",
        )
        p.add_argument(
            "--installed-pkgs",
            action="store_true",
            help="Remove all installed packages if any",
        )
        p.add_argument(
            "--news-read-status",
            action="store_true",
            help="Mark all news items as unread",
        )
        p.add_argument(
            "--progcache",
            action="store_true",
            help="Clear the Ruyi program cache",
        )
        p.add_argument(
            "--repo",
            action="store_true",
            help="Remove the Ruyi repo if located in Ruyi-managed cache directory",
        )
        p.add_argument(
            "--telemetry",
            action="store_true",
            help="Remove all telemetry data recorded if any",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from .self_cli import cli_self_clean

        return cli_self_clean(cfg, args)


class SelfUninstallCommand(
    SelfCommand,
    cmd="uninstall",
    help="Uninstall Ruyi",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--purge",
            action="store_true",
            help="Remove all installed packages and Ruyi-managed remote repo data",
        )
        p.add_argument(
            "-y",
            action="store_true",
            dest="consent",
            help="Give consent for uninstallation on CLI; do not ask for confirmation",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from .self_cli import cli_self_uninstall

        return cli_self_uninstall(cfg, args)


# Version info
# Keep this at the bottom
class VersionCommand(
    RootCommand,
    cmd="version",
    help="Print version information",
):
    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        from .version_cli import cli_version

        return cli_version(cfg, args)


def main(argv: List[str]) -> int:
    gc = GlobalConfig.load_from_config()
    if gc.telemetry is not None:
        gc.telemetry.init_installation(False)
        atexit.register(gc.telemetry.flush)

    if not is_called_as_ruyi(argv[0]):
        from ..mux.runtime import mux_main

        # record an invocation and the command name being proxied to
        if gc.telemetry is not None:
            target = os.path.basename(argv[0])
            gc.telemetry.record("cli:mux-invocation-v1", target=target)

        return mux_main(argv)

    import ruyi
    from .. import log

    p = RootCommand.build_argparse()
    args = p.parse_args(argv[1:])
    ruyi.set_porcelain(args.porcelain)

    nuitka_info = "not compiled"
    if hasattr(ruyi, "__compiled__"):
        nuitka_info = f"__compiled__ = {ruyi.__compiled__}"

    log.D(
        f"__main__.__file__ = {ruyi.main_file()}, sys.executable = {sys.executable}, {nuitka_info}"
    )
    log.D(f"argv[0] = {argv[0]}, self_exe = {ruyi.self_exe()}")
    log.D(f"args={args}")

    func: CLIEntrypoint = args.func

    # record every invocation's subcommand for better insight into usage
    # frequencies
    try:
        telemetry_key = args.tele_key
    except AttributeError:
        log.F("internal error: CLI entrypoint was added without a telemetry key")
        return 1

    if gc.telemetry is not None:
        gc.telemetry.record("cli:invocation-v1", key=telemetry_key)

    try:
        return func(gc, args)
    except Exception:
        raise
