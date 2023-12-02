import argparse
import os
import shutil

import ruyi
from .. import config
from .. import log
from . import user_input


def cli_self_uninstall(args: argparse.Namespace) -> int:
    purge: bool = args.purge
    consent: bool = args.consent
    log.D(f"ruyi self uninstall: purge={purge}, consent={consent}")

    if not ruyi.IS_PACKAGED:
        log.F(
            "this [yellow]ruyi[/yellow] is not in standalone form, and cannot be uninstalled this way"
        )
        return 1

    if not consent:
        if not user_input.ask_for_yesno_confirmation("Continue?"):
            log.I("aborting uninstallation")
            return 0
    else:
        log.I("uninstallation consent given over CLI, proceeding")

    if purge:
        log.I("removing the Ruyi cache")
        cfg = config.GlobalConfig.load_from_config()
        shutil.rmtree(cfg.cache_root, True)

    log.I("removing the ruyi binary")
    os.unlink(ruyi.self_exe())

    log.I("[yellow]ruyi[/yellow] is uninstalled")

    return 0
