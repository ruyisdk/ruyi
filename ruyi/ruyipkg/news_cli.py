import argparse

from rich import box
from rich.table import Table

from ..cli.cmd import RootCommand
from ..config import GlobalConfig
from ..log import RuyiLogger
from ..utils.markdown import RuyiStyledMarkdown
from ..utils.porcelain import PorcelainOutput
from .news import NewsItem, NewsItemContent, NewsItemStore


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
        ord = f"[bold green]{ni.ordinal}[/bold green]" if unread else f"{ni.ordinal}"
        id = f"[bold green]{ni.id}[/bold green]" if unread else ni.id

        tbl.add_row(
            ord,
            id,
            ni.get_content_for_lang(lang).display_title,
        )

    logger.stdout(tbl)


class NewsCommand(
    RootCommand,
    cmd="news",
    has_subcommands=True,
    help="List and read news items from configured repository",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        pass


class NewsListCommand(
    NewsCommand,
    cmd="list",
    help="List news items",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--new",
            action="store_true",
            help="List unread news items only",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        only_unread = args.new

        store = cfg.repo.news_store()
        newsitems = store.list(only_unread)

        if cfg.is_porcelain:
            with PorcelainOutput() as po:
                for ni in newsitems:
                    po.emit(ni.to_porcelain())
            return 0

        logger.stdout("[bold green]News items:[/bold green]\n")
        if not newsitems:
            logger.stdout("  (no unread item)" if only_unread else "  (no item)")
            return 0

        print_news_item_titles(logger, newsitems, cfg.lang_code)

        return 0


class NewsReadCommand(
    NewsCommand,
    cmd="read",
    help="Read news items",
    description="Outputs news item(s) to the console and mark as already read. Defaults to reading all unread items if no item is specified.",
):
    @classmethod
    def configure_args(cls, gc: GlobalConfig, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--quiet",
            "-q",
            action="store_true",
            help="Do not output anything and only mark as read",
        )
        p.add_argument(
            "item",
            type=str,
            nargs="*",
            help="Ordinal or ID of the news item(s) to read",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        quiet = args.quiet
        items_strs = args.item

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
