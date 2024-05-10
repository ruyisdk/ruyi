import argparse

from rich import box
from rich.table import Table

from ..config import GlobalConfig
from ..config.news import NewsReadStatusStore
from ..utils.markdown import MarkdownWithSlimHeadings
from .. import log
from .news import NewsItem
from .repo import MetadataRepo


def print_news_item_titles(
    newsitems: list[NewsItem],
) -> None:
    tbl = Table(box=box.SIMPLE, show_edge=False)
    tbl.add_column("No.")
    tbl.add_column("ID")
    tbl.add_column("Title")

    for ni in newsitems:
        unread = not ni.is_read
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
    for ni in newsitems:
        ni.is_read = ni.id in rs_store

    if only_unread:
        newsitems = [ni for ni in newsitems if not ni.is_read]

    log.stdout("[bold green]News items:[/bold green]\n")
    if not newsitems:
        log.stdout("  (no unread item)" if only_unread else "  (no item)")
        return 0

    print_news_item_titles(newsitems)

    return 0


def cli_news_read(args: argparse.Namespace) -> int:
    quiet = args.quiet
    items_strs = args.item

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(),
        config.get_repo_url(),
        config.get_repo_branch(),
    )

    all_ni = mr.list_newsitems()
    rs_store = config.news_read_status
    rs_store.load()

    # filter out requested news items
    items = filter_news_items_by_specs(all_ni, items_strs, rs_store)
    if items is None:
        return 1

    # render the items
    if not quiet:
        if items:
            for ni in items:
                print_news(ni)
        else:
            log.stdout("No news to display.")

    # record read statuses
    for ni in items:
        rs_store.add(ni.id)
    rs_store.save()

    return 0


def filter_news_items_by_specs(
    all_ni: list[NewsItem],
    specs: list[str],
    rs_store: NewsReadStatusStore,
) -> list[NewsItem] | None:
    if not specs:
        # all unread items
        return [ni for ni in all_ni if ni.id not in rs_store]

    items: list[NewsItem] = []
    ni_by_ord = {ni.ordinal: ni for ni in all_ni}
    ni_by_id = {ni.id: ni for ni in all_ni}
    for i in specs:
        try:
            ni_ord = int(i)
            if ni_ord not in ni_by_ord:
                log.F(f"there is no news item with ordinal {ni_ord}")
                return None
            items.append(ni_by_ord[ni_ord])
        except ValueError:
            # treat i as id
            if i not in ni_by_id:
                log.F(f"there is no news item with ID '{i}'")
                return None
            items.append(ni_by_id[i])

    return items


def print_news(ni: NewsItem) -> None:
    md = MarkdownWithSlimHeadings(ni.content)
    log.stdout(md)
    log.stdout("")
