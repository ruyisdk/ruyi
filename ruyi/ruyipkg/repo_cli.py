import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand
from ..i18n import _

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class RepoCommand(
    RootCommand,
    cmd="repo",
    has_subcommands=True,
    help=_("Manage configured package repositories"),
):
    @classmethod
    def configure_args(
        cls,
        gc: "GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        pass


class RepoListCommand(
    RepoCommand,
    cmd="list",
    help=_("List configured package repositories"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .repo import DEFAULT_REPO_ID

        entries = cfg.repo_entries
        logger = cfg.logger

        for entry in sorted(entries, key=lambda e: -e.priority):
            active_marker = "*" if entry.active else " "
            default_marker = " (default)" if entry.id == DEFAULT_REPO_ID else ""

            source = entry.remote or ""
            if entry.local_path:
                source = entry.local_path if not source else f"{source} (local: {entry.local_path})"

            logger.stdout(
                f"  {active_marker} [bold]{entry.id}[/]{default_marker}  "
                f"priority={entry.priority}  {source}"
            )

        return 0
