import argparse

from ..config import GlobalConfig
from .. import log
from . import news_cli
from .repo import MetadataRepo


def cli_update(args: argparse.Namespace) -> int:
    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )
    mr.sync()

    # check if there are new newsitems
    rs_store = config.news_read_status
    rs_store.load()
    unread_newsitems = [ni for ni in mr.list_newsitems() if ni.id not in rs_store]
    if unread_newsitems:
        log.stdout(f"\nThere are {len(unread_newsitems)} new news item(s):\n")
        news_cli.print_news_item_titles(unread_newsitems, rs_store)
        log.stdout("\nYou can read them with [yellow]ruyi news read[/yellow].")

    return 0
