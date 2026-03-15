import argparse
import pathlib
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


class RepoAddCommand(
    RepoCommand,
    cmd="add",
    help=_("Add a package repository"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument("id", type=str, help=_("unique repository identifier"))
        p.add_argument("url", type=str, nargs="?", default=None, help=_("git remote URL"))
        p.add_argument("--branch", type=str, default=None, help=_("git branch to track"))
        p.add_argument("--priority", type=int, default=0, help=_("priority (higher = overrides lower)"))
        p.add_argument("--local", type=str, default=None, help=_("local path to use instead of or alongside remote"))
        p.add_argument("--name", type=str, default=None, help=_("human-readable name for the repo"))

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor
        from ..config.schema import (
            KEY_REPOS_ACTIVE,
            KEY_REPOS_BRANCH,
            KEY_REPOS_ID,
            KEY_REPOS_LOCAL,
            KEY_REPOS_NAME,
            KEY_REPOS_PRIORITY,
            KEY_REPOS_REMOTE,
        )
        from .repo import DEFAULT_REPO_ID, REPO_ID_PATTERN

        logger = cfg.logger
        repo_id: str = args.id
        url: str | None = args.url
        local: str | None = args.local

        if not REPO_ID_PATTERN.match(repo_id):
            logger.F(
                _("invalid repo id '{id}'").format(id=repo_id)
            )
            return 1

        if repo_id == DEFAULT_REPO_ID:
            logger.F(
                _("'{id}' is reserved; use [repo] config to configure the default repository").format(
                    id=DEFAULT_REPO_ID,
                )
            )
            return 1

        if not url and not local:
            logger.F(_("at least one of URL or --local must be provided"))
            return 1

        if local and not pathlib.Path(local).is_absolute():
            logger.F(
                _("local path '{path}' must be absolute").format(path=local)
            )
            return 1

        # Check for conflict with existing entries.
        for entry in cfg.repo_entries:
            if entry.id == repo_id:
                logger.F(
                    _("a repo with id '{id}' already exists").format(id=repo_id)
                )
                return 1

        entry_data: dict[str, object] = {KEY_REPOS_ID: repo_id}
        if args.name:
            entry_data[KEY_REPOS_NAME] = args.name
        if url:
            entry_data[KEY_REPOS_REMOTE] = url
        if args.branch:
            entry_data[KEY_REPOS_BRANCH] = args.branch
        if local:
            entry_data[KEY_REPOS_LOCAL] = local
        if args.priority != 0:
            entry_data[KEY_REPOS_PRIORITY] = args.priority
        entry_data[KEY_REPOS_ACTIVE] = True

        with ConfigEditor.work_on_user_local_config(cfg) as editor:
            editor.add_repos_entry(entry_data)
            editor.stage()

        logger.I(
            _("repo '{id}' added; run 'ruyi update' to sync").format(id=repo_id)
        )
        return 0
