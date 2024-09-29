import argparse
import os
import shutil

import ruyi
from .. import config
from .. import log
from . import user_input

UNINSTALL_NOTICE = """
[bold]Thanks for hacking with [yellow]Ruyi[/yellow]![/bold]

This will uninstall [yellow]Ruyi[/yellow] from your system, and optionally remove
all installed packages and [yellow]Ruyi[/yellow]-managed repository data if the
[green]--purge[/green] switch is given on the command line.

Note that your [yellow]Ruyi[/yellow] virtual environments [bold]will become unusable[/bold] after
[yellow]Ruyi[/yellow] is uninstalled. You should take care of migrating or cleaning
them yourselves afterwards.
"""


def cli_self_uninstall(cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
    purge: bool = args.purge
    consent: bool = args.consent
    log.D(f"ruyi self uninstall: purge={purge}, consent={consent}")

    if cfg.is_installation_externally_managed:
        log.F(
            "this [yellow]ruyi[/] is externally managed, for example, by the system package manager, and cannot be uninstalled this way"
        )
        log.I("please uninstall via the external manager instead")
        return 1

    if not ruyi.IS_PACKAGED:
        log.F(
            "this [yellow]ruyi[/yellow] is not in standalone form, and cannot be uninstalled this way"
        )
        return 1

    if not consent:
        log.stdout(UNINSTALL_NOTICE)
        if not user_input.ask_for_yesno_confirmation("Continue?"):
            log.I("aborting uninstallation")
            return 0
    else:
        log.I("uninstallation consent given over CLI, proceeding")

    _do_reset(
        cfg,
        installed_pkgs=purge,
        all_state=purge,
        all_cache=purge,
        self_binary=True,
    )

    log.I("[yellow]ruyi[/yellow] is uninstalled")

    return 0


def _do_reset(
    cfg: config.GlobalConfig,
    *,
    installed_pkgs: bool = False,
    all_state: bool = False,
    all_cache: bool = False,
    self_binary: bool = False,
) -> None:
    if installed_pkgs:
        log.I("removing installed packages")
        shutil.rmtree(cfg.data_root, True)

    if all_state:
        log.I("removing state data")
        shutil.rmtree(cfg.state_root, True)

    if all_cache:
        log.I("removing cached data")
        shutil.rmtree(cfg.cache_root, True)

    if self_binary:
        log.I("removing the ruyi binary")
        try:
            os.unlink(ruyi.self_exe())
        except FileNotFoundError:
            # we might have already removed ourselves during the purge; nothing to
            # do now.
            pass
