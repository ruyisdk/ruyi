import argparse

from ..config import GlobalConfig
from .. import log
from ..version import COPYRIGHT_NOTICE, RUYI_SEMVER


def cli_version(gc: GlobalConfig, args: argparse.Namespace) -> int:
    from ..ruyipkg.host import get_native_host

    print(f"Ruyi {RUYI_SEMVER}\n\nRunning on {get_native_host()}.")

    if gc.is_installation_externally_managed:
        print("This Ruyi installation is externally managed.")

    print()

    log.stdout(COPYRIGHT_NOTICE)

    return 0
