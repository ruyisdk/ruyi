import argparse

from .. import log
from ..version import COPYRIGHT_NOTICE, RUYI_SEMVER


def cli_version(_: argparse.Namespace) -> int:
    from ..ruyipkg.host import get_native_host

    print(f"Ruyi {RUYI_SEMVER}\n\nRunning on {get_native_host()}.\n")
    log.stdout(COPYRIGHT_NOTICE)

    return 0
