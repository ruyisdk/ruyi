import argparse

import ruyi
from .. import log


def cli_self_uninstall(args: argparse.Namespace) -> int:
    purge: bool = args.purge
    consent: bool = args.consent
    log.D(f"ruyi self uninstall: purge={purge}, consent={consent}")

    if not ruyi.IS_PACKAGED:
        log.F(
            "this [yellow]ruyi[/yellow] is not in standalone form, and cannot be uninstalled this way"
        )
        return 1

    # TODO

    return 0
