import argparse

from .. import log
from ..config import GlobalConfig
from ..version import COPYRIGHT_NOTICE, RUYI_SEMVER
from .cmd import RootCommand


class VersionCommand(
    RootCommand,
    cmd="version",
    help="Print version information",
):
    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        return cli_version(cfg, args)


def cli_version(cfg: GlobalConfig, args: argparse.Namespace) -> int:
    from ..ruyipkg.host import get_native_host

    print(f"Ruyi {RUYI_SEMVER}\n\nRunning on {get_native_host()}.")

    if cfg.is_installation_externally_managed:
        print("This Ruyi installation is externally managed.")

    print()

    log.stdout(COPYRIGHT_NOTICE)

    return 0
