import argparse

from rich import box
from rich.table import Table


from ..config import GlobalConfig
from ..config.news import NewsReadStatusStore
from .. import log
from .news import NewsItem
from .repo import MetadataRepo


def print_news_item_titles(
    newsitems: list[NewsItem],
    rs_store: NewsReadStatusStore,
) -> None:
    tbl = Table(box=box.SIMPLE, show_edge=False)
    tbl.add_column("No.")
    tbl.add_column("ID")
    tbl.add_column("Title")

    for ni in newsitems:
        unread = ni.id not in rs_store
        ord = f"[bold green]{ni.ordinal}[/bold green]" if unread else f"{ni.ordinal}"
        id = f"[bold green]{ni.id}[/bold green]" if unread else ni.id

        tbl.add_row(
            ord,
            id,
            ni.display_title,
        )

    log.stdout(tbl)


def cli_news_list(args: argparse.Namespace) -> int:
    only_unread = args.new

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(),
        config.get_repo_url(),
        config.get_repo_branch(),
    )

    newsitems = mr.list_newsitems()
    rs_store = config.news_read_status
    rs_store.load()

    if only_unread:
        newsitems = [ni for ni in newsitems if ni.id not in rs_store]

    log.stdout("[bold green]News items:[/bold green]\n")
    if not newsitems:
        log.stdout("  (no unread item)" if only_unread else "  (no item)")
        return 0

    print_news_item_titles(newsitems, rs_store)

    return 0


def cli_news_read(_: argparse.Namespace) -> int:
    # TODO
    return 0
