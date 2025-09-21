from rich import box
from rich.table import Table

from ..config import GlobalConfig
from ..log import RuyiLogger
from ..utils.markdown import RuyiStyledMarkdown
from ..utils.porcelain import PorcelainOutput
from .news_store import NewsItem, NewsItemContent, NewsItemStore


def print_news_item_titles(
    logger: RuyiLogger,
    newsitems: list[NewsItem],
    lang: str,
) -> None:
    tbl = Table(box=box.SIMPLE, show_edge=False)
    tbl.add_column("No.")
    tbl.add_column("ID")
    tbl.add_column("Title")

    for ni in newsitems:
        unread = not ni.is_read
        ord = f"[bold green]{ni.ordinal}[/]" if unread else f"{ni.ordinal}"
        id = f"[bold green]{ni.id}[/]" if unread else ni.id

        tbl.add_row(
            ord,
            id,
            ni.get_content_for_lang(lang).display_title,
        )

    logger.stdout(tbl)


def maybe_notify_unread_news(
    gc: GlobalConfig,
    prompt_no_unread: bool = True,
) -> None:
    """Check if there are new newsitems, notify the user if so."""

    unread_newsitems = gc.repo.news_store().list(True)
    if unread_newsitems:
        gc.logger.stdout(f"\nThere are {len(unread_newsitems)} new news item(s):\n")
        print_news_item_titles(gc.logger, unread_newsitems, gc.lang_code)
        gc.logger.stdout("\nYou can read them with [yellow]ruyi news read[/].")
        return

    if prompt_no_unread:
        gc.logger.stdout(
            "\nAll news items have been read. To see a list of them, run [yellow]ruyi news list[/].\n"
        )


def do_news_list(
    cfg: GlobalConfig,
    only_unread: bool,
) -> int:
    logger = cfg.logger
    store = cfg.repo.news_store()
    newsitems = store.list(only_unread)

    if cfg.is_porcelain:
        with PorcelainOutput() as po:
            for ni in newsitems:
                po.emit(ni.to_porcelain())
        return 0

    logger.stdout("[bold green]News items:[/]\n")
    if not newsitems:
        logger.stdout("  (no unread item)" if only_unread else "  (no item)")
        return 0

    print_news_item_titles(logger, newsitems, cfg.lang_code)

    return 0


def do_news_read(
    cfg: GlobalConfig,
    quiet: bool,
    items_strs: list[str],
) -> int:
    logger = cfg.logger
    store = cfg.repo.news_store()

    # filter out requested news items
    items = filter_news_items_by_specs(logger, store, items_strs)
    if items is None:
        return 1

    if cfg.is_porcelain:
        with PorcelainOutput() as po:
            for ni in items:
                po.emit(ni.to_porcelain())
    elif not quiet:
        # render the items
        if items:
            for ni in items:
                print_news(logger, ni.get_content_for_lang(cfg.lang_code))
        else:
            logger.stdout("No news to display.")

    # record read statuses
    store.mark_as_read(*(ni.id for ni in items))

    return 0


def filter_news_items_by_specs(
    logger: RuyiLogger,
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
                logger.F(f"there is no news item with ordinal {ni_ord}")
                return None
            items.append(ni_by_ord[ni_ord])
        except ValueError:
            # treat i as id
            if i not in ni_by_id:
                logger.F(f"there is no news item with ID '{i}'")
                return None
            items.append(ni_by_id[i])

    return items


def print_news(logger: RuyiLogger, nic: NewsItemContent) -> None:
    md = RuyiStyledMarkdown(nic.content)
    logger.stdout(md)
    logger.stdout("")
