import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class UpdateCommand(
    RootCommand,
    cmd="update",
    help="Update RuyiSDK repo and packages",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from . import news
        from .state import BoundInstallationStateStore

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

        news.maybe_notify_unread_news(cfg, False)

        return 0
