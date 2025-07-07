import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand
from .list_filter import ListFilter, ListFilterAction

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class ListCommand(
    RootCommand,
    cmd="list",
    has_subcommands=True,
    is_subcommand_required=False,
    has_main=True,
    help="List available packages in configured repository",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Also show details for every package",
        )

        # filter expressions
        p.add_argument(
            "--is-installed",
            action=ListFilterAction,
            nargs=1,
            dest="filters",
            help="Match packages that are installed (y/true/1) or not installed (n/false/0)",
        )
        p.add_argument(
            "--category-contains",
            action=ListFilterAction,
            nargs=1,
            dest="filters",
            help="Match packages from categories whose names contain the given string",
        )
        p.add_argument(
            "--category-is",
            action=ListFilterAction,
            nargs=1,
            dest="filters",
            help="Match packages from the given category",
        )
        p.add_argument(
            "--name-contains",
            action=ListFilterAction,
            nargs=1,
            dest="filters",
            help="Match packages whose names contain the given string",
        )

        if gc.is_experimental:
            p.add_argument(
                "--related-to-entity",
                action=ListFilterAction,
                nargs=1,
                dest="filters",
                help="Match packages related to the given entity",
            )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .list import do_list

        verbose: bool = args.verbose
        filters: ListFilter = args.filters

        return do_list(
            cfg,
            filters=filters,
            verbose=verbose,
        )
