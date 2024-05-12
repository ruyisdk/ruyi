import argparse

from rich import box
from rich.table import Table

from ..config import GlobalConfig
from ..utils.markdown import MarkdownWithSlimHeadings
from ..utils.porcelain import PorcelainOutput
from .. import is_porcelain, log
from .news import NewsItem, NewsItemContent, NewsItemStore
from .repo import MetadataRepo


def print_news_item_titles(
    newsitems: list[NewsItem],
    lang: str,
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
            ni.get_content_for_lang(lang).display_title,
        )

    log.stdout(tbl)


def cli_news_list(args: argparse.Namespace) -> int:
    only_unread = args.new

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)
    store = mr.news_store()
    newsitems = store.list(only_unread)

    if is_porcelain():
        with PorcelainOutput() as po:
            for ni in newsitems:
                po.emit(ni.to_porcelain())
        return 0

    log.stdout("[bold green]News items:[/bold green]\n")
    if not newsitems:
        log.stdout("  (no unread item)" if only_unread else "  (no item)")
        return 0

    print_news_item_titles(newsitems, config.lang_code)

    return 0


def cli_news_read(args: argparse.Namespace) -> int:
    quiet = args.quiet
    items_strs = args.item

    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)
    store = mr.news_store()

    # filter out requested news items
    items = filter_news_items_by_specs(store, items_strs)
    if items is None:
        return 1

    # render the items
    if not quiet:
        if items:
            for ni in items:
                print_news(ni.get_content_for_lang(config.lang_code))
        else:
            log.stdout("No news to display.")

    # record read statuses
    store.mark_as_read(*(ni.id for ni in items))

    return 0


def filter_news_items_by_specs(
    store: NewsItemStore,
    specs: list[str],
) -> list[NewsItem] | None:
    if not specs:
        # all unread items
        return store.list(True)

    all_ni = store.list(False)
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


def print_news(nic: NewsItemContent) -> None:
    md = MarkdownWithSlimHeadings(nic.content)
    log.stdout(md)
    log.stdout("")
