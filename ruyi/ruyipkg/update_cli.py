import argparse

from ..config import GlobalConfig
from .. import log
from . import news_cli
from .repo import MetadataRepo


def cli_update(config: GlobalConfig, args: argparse.Namespace) -> int:
    mr = MetadataRepo(config)
    mr.sync()

    # check if there are new newsitems
    unread_newsitems = mr.news_store().list(True)
    if unread_newsitems:
        log.stdout(f"\nThere are {len(unread_newsitems)} new news item(s):\n")
        news_cli.print_news_item_titles(unread_newsitems, config.lang_code)
        log.stdout("\nYou can read them with [yellow]ruyi news read[/yellow].")

    return 0
