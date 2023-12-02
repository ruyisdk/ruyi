import argparse
import os
import platform
from typing import List

import ruyi
from .. import log
from ..mux.runtime import mux_main
from .prereqs import check_dep_binaries

RUYI_ENTRYPOINT_NAME = "ruyi"


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0) in {RUYI_ENTRYPOINT_NAME, "__main__.py"}


def init_debug_status() -> None:
    debug_env = os.environ.get("RUYI_DEBUG", "")
    ruyi.set_debug(debug_env.lower() in {"1", "true", "x", "y", "yes"})


def init_argparse() -> argparse.ArgumentParser:
    from ..mux.venv import cli_venv
    from ..ruyipkg.admin_cli import cli_admin_manifest
    from ..ruyipkg.pkg_cli import cli_extract, cli_install, cli_list
    from ..ruyipkg.profile_cli import cli_list_profiles
    from ..ruyipkg.update import cli_update
    from .self_cli import cli_self_uninstall
    from .version_cli import cli_version

    root = argparse.ArgumentParser(
        prog=RUYI_ENTRYPOINT_NAME,
        description="RuyiSDK Package Manager",
    )

    sp = root.add_subparsers(
        required=True,
        title="subcommands",
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
        default=platform.machine(),
        help="Override the host architecture (normally not needed)",
    )
    extract.set_defaults(func=cli_extract)

    install = sp.add_parser(
        "install", aliases=["i"], help="Install package from configured repository"
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
        default=platform.machine(),
        help="Override the host architecture (normally not needed)",
    )
    install.add_argument(
        "--reinstall",
        action="store_true",
        help="Force re-installation of already installed packages",
    )
    install.set_defaults(func=cli_install)

    list = sp.add_parser(
        "list", help="List available packages in configured repository"
    )
    list.set_defaults(func=cli_list)
    list.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Also show details for every package",
    )

    listsp = list.add_subparsers(required=False)
    list_profiles = listsp.add_parser("profiles", help="List all available profiles")
    list_profiles.set_defaults(func=cli_list_profiles)

    up = sp.add_parser("update", help="Update RuyiSDK repo and packages")
    up.set_defaults(func=cli_update)

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
        help="Specifier (atom) of the toolchain to use",
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

    venv.set_defaults(func=cli_venv)

    # Repo admin commands
    admin = sp.add_parser(
        "admin",
        # https://github.com/python/cpython/issues/67037
        # help=argparse.SUPPRESS,
        help="(NOT FOR REGULAR USERS) Subcommands for managing Ruyi repos",
    )
    adminsp = admin.add_subparsers(required=True)

    admin_manifest = adminsp.add_parser(
        "manifest",
        help="Generate manifest for the distfiles given",
    )
    admin_manifest.add_argument(
        "file",
        type=str,
        nargs="+",
        help="Path to the distfile(s) to generate manifest for",
    )
    admin_manifest.set_defaults(func=cli_admin_manifest)

    # Self-management commands
    self = sp.add_parser(
        "self",
        help="Manage this Ruyi installation",
    )
    selfsp = self.add_subparsers(required=True)

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
    self_uninstall.set_defaults(func=cli_self_uninstall)

    # Version info
    # Keep this at the bottom
    version = sp.add_parser(
        "version",
        help="Print version information",
    )
    version.set_defaults(func=cli_version)

    return root



def main(argv: List[str]) -> int:
    if not is_called_as_ruyi(argv[0]):
        return mux_main(argv)

    check_dep_binaries()

    p = init_argparse()
    args = p.parse_args(argv[1:])
    log.D(f"args={args}")

    try:
        return args.func(args)
    except Exception as e:
        # print(f"[bold red]fatal error:[/bold red] no command specified {e}")
        # return 1
        raise

    return 0
