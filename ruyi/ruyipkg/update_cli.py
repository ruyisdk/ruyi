import argparse

from ..config import GlobalConfig
from ..cli.cmd import RootCommand
from . import news_cli
from .state import BoundInstallationStateStore


class UpdateCommand(
    RootCommand,
    cmd="update",
    help="Update RuyiSDK repo and packages",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        mr = cfg.repo
        mr.sync()

        # check for upgradable packages
        bis = BoundInstallationStateStore(cfg.ruyipkg_global_state, mr)
        upgradable = list(bis.iter_upgradable_pkgs(cfg.include_prereleases))

        if upgradable:
            logger.stdout(
                "\nNewer versions are available for some of your installed packages:\n"
            )
            for pm, new_ver in upgradable:
                logger.stdout(
                    f"  - [bold]{pm.category}/{pm.name}[/]: [yellow]{pm.ver}[/] -> [green]{new_ver}[/]"
                )
            logger.stdout(
                """
Re-run [yellow]ruyi install[/] to upgrade, and don't forget to re-create any affected
virtual environments."""
            )

        # check if there are new newsitems
        unread_newsitems = mr.news_store().list(True)
        if unread_newsitems:
            logger.stdout(f"\nThere are {len(unread_newsitems)} new news item(s):\n")
            news_cli.print_news_item_titles(logger, unread_newsitems, cfg.lang_code)
            logger.stdout("\nYou can read them with [yellow]ruyi news read[/].")

        return 0
