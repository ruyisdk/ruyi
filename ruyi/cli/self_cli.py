import argparse
import os
import pathlib
import shutil

import ruyi
from .. import config
from .. import log
from . import user_input
from .cmd import RootCommand

UNINSTALL_NOTICE = """
[bold]Thanks for hacking with [yellow]Ruyi[/yellow]![/bold]

This will uninstall [yellow]Ruyi[/yellow] from your system, and optionally remove
all installed packages and [yellow]Ruyi[/yellow]-managed repository data if the
[green]--purge[/green] switch is given on the command line.

Note that your [yellow]Ruyi[/yellow] virtual environments [bold]will become unusable[/bold] after
[yellow]Ruyi[/yellow] is uninstalled. You should take care of migrating or cleaning
them yourselves afterwards.
"""


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
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
        quiet: bool = args.quiet
        all: bool = args.all
        distfiles: bool = args.distfiles
        installed_pkgs: bool = args.installed_pkgs
        news_read_status: bool = args.news_read_status
        progcache: bool = args.progcache
        repo: bool = args.repo
        telemetry: bool = args.telemetry

        if all:
            distfiles = True
            installed_pkgs = True
            news_read_status = True
            progcache = True
            repo = True
            telemetry = True

        if not any(
            [
                distfiles,
                installed_pkgs,
                news_read_status,
                progcache,
                repo,
                telemetry,
            ]
        ):
            log.F("no data specified for cleaning")
            log.I(
                "please check [yellow]ruyi self clean --help[/] for a list of cleanable data"
            )
            return 1

        _do_reset(
            cfg,
            quiet=quiet,
            distfiles=distfiles,
            installed_pkgs=installed_pkgs,
            news_read_status=news_read_status,
            progcache=progcache,
            repo=repo,
            telemetry=telemetry,
        )

        return 0


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
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
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
            quiet=False,
            installed_pkgs=purge,
            all_state=purge,
            all_cache=purge,
            self_binary=True,
        )

        log.I("[yellow]ruyi[/yellow] is uninstalled")

        return 0


def _do_reset(
    cfg: config.GlobalConfig,
    quiet: bool = False,
    *,
    installed_pkgs: bool = False,
    all_state: bool = False,
    news_read_status: bool = False,  # ignored if all_state=True
    telemetry: bool = False,  # ignored if all_state=True
    all_cache: bool = False,
    distfiles: bool = False,  # ignored if all_cache=True
    progcache: bool = False,  # ignored if all_cache=True
    repo: bool = False,  # ignored if all_cache=True
    self_binary: bool = False,
) -> None:
    def status(s: str) -> None:
        if quiet:
            return
        log.I(s)

    if installed_pkgs:
        status("removing installed packages")
        shutil.rmtree(cfg.data_root, True)

    # do not record any telemetry data if we're purging it
    if all_state or telemetry:
        if tm := cfg.telemetry:
            tm.discard_events(True)

    if all_state:
        status("removing state data")
        shutil.rmtree(cfg.state_root, True)
    else:
        if news_read_status:
            status("removing read status of news items")
            cfg.news_read_status.remove()

        if telemetry:
            status("removing all telemetry data")
            shutil.rmtree(cfg.telemetry_root, True)

    if all_cache:
        status("removing cached data")
        shutil.rmtree(cfg.cache_root, True)
    else:
        if distfiles:
            status("removing downloaded distfiles")
            # TODO: deduplicate the path derivation
            shutil.rmtree(os.path.join(cfg.cache_root, "distfiles"), True)

        if progcache:
            status("clearing the Ruyi program cache")
            # TODO: deduplicate the path derivation
            shutil.rmtree(os.path.join(cfg.cache_root, "progcache"), True)

        if repo:
            # for safety, don't remove the repo if it's outside of Ruyi's XDG
            # cache root
            repo_dir = pathlib.Path(cfg.get_repo_dir()).resolve()
            cache_root = pathlib.Path(cfg.cache_root).resolve()

            repo_is_below_cache_root = False
            for p in repo_dir.parents:
                if p == cache_root:
                    repo_is_below_cache_root = True
                    break

            if not repo_is_below_cache_root:
                log.W(
                    "not removing the Ruyi repo: it is outside of the Ruyi cache directory"
                )
            else:
                status("removing the Ruyi repo")
                shutil.rmtree(repo_dir, True)

    if self_binary:
        status("removing the ruyi binary")
        try:
            os.unlink(ruyi.self_exe())
        except FileNotFoundError:
            # we might have already removed ourselves during the purge; nothing to
            # do now.
            pass
