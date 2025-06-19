import argparse

from ..config import GlobalConfig
from ..cli.cmd import RootCommand
from . import news_cli


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

        # check if there are new newsitems
        unread_newsitems = mr.news_store().list(True)
        if unread_newsitems:
            logger.stdout(f"\nThere are {len(unread_newsitems)} new news item(s):\n")
            news_cli.print_news_item_titles(logger, unread_newsitems, cfg.lang_code)
            logger.stdout("\nYou can read them with [yellow]ruyi news read[/].")

        return 0
