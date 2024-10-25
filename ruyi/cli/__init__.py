import argparse
import atexit
import os
import sys
from typing import Callable, IO, List, Protocol

from ..config import GlobalConfig

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


def init_argparse() -> argparse.ArgumentParser:
    from ..device.provision_cli import cli_device_provision
    from ..mux.venv.venv_cli import cli_venv
    from ..ruyipkg.admin_cli import cli_admin_format_manifest, cli_admin_manifest
    from ..ruyipkg.host import get_native_host
    from ..ruyipkg.news_cli import cli_news_list, cli_news_read
    from ..ruyipkg.pkg_cli import cli_extract, cli_install, cli_list
    from ..ruyipkg.profile_cli import cli_list_profiles
    from ..ruyipkg.update_cli import cli_update
    from ..version import RUYI_SEMVER
    from .self_cli import cli_self_clean, cli_self_uninstall
    from .version_cli import cli_version

    native_host_str = get_native_host()

    root = argparse.ArgumentParser(
        prog=RUYI_ENTRYPOINT_NAME,
        description=f"RuyiSDK Package Manager {RUYI_SEMVER}",
    )
    root.set_defaults(func=_wrap_help(root), tele_key="<bare>")

    root.add_argument(
        "-V",
        "--version",
        action="store_const",
        dest="func",
        const=cli_version,
        help="Print version information",
    )

    root.add_argument(
        "--porcelain",
        action="store_true",
        help="Give the output in a machine-friendly format if applicable",
    )

    sp = root.add_subparsers(
        title="subcommands",
    )

    # Device management commands
    device = sp.add_parser(
        "device",
        help="Manage devices",
    )
    device.set_defaults(func=_wrap_help(device), tele_key="device")
    devicesp = device.add_subparsers(
        title="subcommands",
    )

    device_provision = devicesp.add_parser(
        "provision",
        help="Interactively initialize a device for development",
    )
    device_provision.set_defaults(
        func=cli_device_provision,
        tele_key="device provision",
    )

    extract = sp.add_parser(
        "extract",
        help="Fetch package(s) then extract to current directory",
    )
    extract.add_argument(
        "atom",
        type=str,
        nargs="+",
        help="Specifier (atom) of the package(s) to extract",
    )
    extract.add_argument(
        "--host",
        type=str,
        default=native_host_str,
        help="Override the host architecture (normally not needed)",
    )
    extract.set_defaults(func=cli_extract, tele_key="extract")

    install = sp.add_parser(
        "install",
        aliases=["i"],
        help="Install package from configured repository",
    )
    install.add_argument(
        "atom",
        type=str,
        nargs="+",
        help="Specifier (atom) of the package to install",
    )
    install.add_argument(
        "-f",
        "--fetch-only",
        action="store_true",
        help="Fetch distribution files only without installing",
    )
    install.add_argument(
        "--host",
        type=str,
        default=native_host_str,
        help="Override the host architecture (normally not needed)",
    )
    install.add_argument(
        "--reinstall",
        action="store_true",
        help="Force re-installation of already installed packages",
    )
    install.set_defaults(func=cli_install, tele_key="install")

    list = sp.add_parser(
        "list", help="List available packages in configured repository"
    )
    list.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Also show details for every package",
    )
    list.set_defaults(func=cli_list, tele_key="list")

    listsp = list.add_subparsers(required=False)
    list_profiles = listsp.add_parser("profiles", help="List all available profiles")
    list_profiles.set_defaults(func=cli_list_profiles, tele_key="list profiles")

    news = sp.add_parser(
        "news",
        help="List and read news items from configured repository",
    )
    news.set_defaults(func=_wrap_help(news), tele_key="news")
    newssp = news.add_subparsers(title="subcommands")

    news_list = newssp.add_parser(
        "list",
        help="List news items",
    )
    news_list.add_argument(
        "--new",
        action="store_true",
        help="List unread news items only",
    )
    news_list.set_defaults(func=cli_news_list, tele_key="news list")

    news_read = newssp.add_parser(
        "read",
        help="Read news items",
        description="Outputs news item(s) to the console and mark as already read. Defaults to reading all unread items if no item is specified.",
    )
    news_read.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Do not output anything and only mark as read",
    )
    news_read.add_argument(
        "item",
        type=str,
        nargs="*",
        help="Ordinal or ID of the news item(s) to read",
    )
    news_read.set_defaults(func=cli_news_read, tele_key="news read")

    up = sp.add_parser("update", help="Update RuyiSDK repo and packages")
    up.set_defaults(func=cli_update, tele_key="update")

    venv = sp.add_parser(
        "venv",
        help="Generate a virtual environment adapted to the chosen toolchain and profile",
    )
    venv.add_argument("profile", type=str, help="Profile to use for the environment")
    venv.add_argument("dest", type=str, help="Path to the new virtual environment")
    venv.add_argument(
        "--name",
        "-n",
        type=str,
        default=None,
        help="Override the venv's name",
    )
    venv.add_argument(
        "--toolchain",
        "-t",
        type=str,
        action="append",
        help="Specifier(s) (atoms) of the toolchain package(s) to use",
    )
    venv.add_argument(
        "--emulator",
        "-e",
        type=str,
        help="Specifier (atom) of the emulator package to use",
    )
    venv.add_argument(
        "--with-sysroot",
        action="store_true",
        dest="with_sysroot",
        default=True,
        help="Provision a fresh sysroot inside the new virtual environment (default)",
    )
    venv.add_argument(
        "--without-sysroot",
        action="store_false",
        dest="with_sysroot",
        help="Do not include a sysroot inside the new virtual environment",
    )
    venv.add_argument(
        "--sysroot-from",
        type=str,
        help="Specifier (atom) of the sysroot package to use, in favor of the toolchain-included one if applicable",
    )
    venv.set_defaults(func=cli_venv, tele_key="venv")

    # Repo admin commands
    admin = sp.add_parser(
        "admin",
        # https://github.com/python/cpython/issues/67037
        # help=argparse.SUPPRESS,
        help="(NOT FOR REGULAR USERS) Subcommands for managing Ruyi repos",
    )
    admin.set_defaults(func=_wrap_help(admin), tele_key="admin")
    adminsp = admin.add_subparsers(
        title="subcommands",
    )

    admin_format_manifest = adminsp.add_parser(
        "format-manifest",
        help="Format the given package manifests into canonical TOML representation",
    )
    admin_format_manifest.add_argument(
        "file",
        type=str,
        nargs="+",
        help="Path to the distfile(s) to generate manifest for",
    )
    admin_format_manifest.set_defaults(
        func=cli_admin_format_manifest,
        tele_key="admin format-manifest",
    )

    admin_manifest = adminsp.add_parser(
        "manifest",
        help="Generate manifest for the distfiles given",
    )
    admin_manifest.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["json", "toml"],
        default="json",
        help="Format of manifest to generate",
    )
    admin_manifest.add_argument(
        "--restrict",
        type=str,
        default="",
        help="the 'restrict' field to use for all mentioned distfiles, separated with comma",
    )
    admin_manifest.add_argument(
        "file",
        type=str,
        nargs="+",
        help="Path to the distfile(s) to generate manifest for",
    )
    admin_manifest.set_defaults(func=cli_admin_manifest, tele_key="admin manifest")

    # Self-management commands
    self = sp.add_parser(
        "self",
        help="Manage this Ruyi installation",
    )
    self.set_defaults(func=_wrap_help(self), tele_key="self")
    selfsp = self.add_subparsers(
        title="subcommands",
    )

    self_clean = selfsp.add_parser(
        "clean",
        help="Remove various Ruyi-managed data to reclaim storage",
    )
    self_clean.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Do not print out the actions being performed",
    )
    self_clean.add_argument(
        "--all",
        action="store_true",
        help="Remove all covered data",
    )
    self_clean.add_argument(
        "--distfiles",
        action="store_true",
        help="Remove all downloaded distfiles if any",
    )
    self_clean.add_argument(
        "--installed-pkgs",
        action="store_true",
        help="Remove all installed packages if any",
    )
    self_clean.add_argument(
        "--progcache",
        action="store_true",
        help="Clear the Ruyi program cache",
    )
    self_clean.add_argument(
        "--repo",
        action="store_true",
        help="Remove the Ruyi repo if located in Ruyi-managed cache directory",
    )
    self_clean.add_argument(
        "--telemetry",
        action="store_true",
        help="Remove all telemetry data recorded if any",
    )
    self_clean.set_defaults(func=cli_self_clean, tele_key="self clean")

    self_uninstall = selfsp.add_parser(
        "uninstall",
        help="Uninstall Ruyi",
    )
    self_uninstall.add_argument(
        "--purge",
        action="store_true",
        help="Remove all installed packages and Ruyi-managed remote repo data",
    )
    self_uninstall.add_argument(
        "-y",
        action="store_true",
        dest="consent",
        help="Give consent for uninstallation on CLI; do not ask for confirmation",
    )
    self_uninstall.set_defaults(func=cli_self_uninstall, tele_key="self uninstall")

    # Version info
    # Keep this at the bottom
    version = sp.add_parser(
        "version",
        help="Print version information",
    )
    version.set_defaults(func=cli_version, tele_key="version")

    return root


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

    p = init_argparse()
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
