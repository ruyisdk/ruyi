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
        from .repo import do_repo_list
        return do_repo_list(cfg, args)


class RepoAddCommand(
    RepoCommand,
    cmd="add",
    help=_("Add a package repository"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument("id", type=str, help=_("unique repository identifier"))
        p.add_argument(
            "url", type=str, nargs="?", default=None, help=_("git remote URL")
        )
        p.add_argument(
            "--branch", type=str, default=None, help=_("git branch to track")
        )
        p.add_argument(
            "--priority",
            type=int,
            default=0,
            help=_("priority (higher = overrides lower)"),
        )
        p.add_argument(
            "--local",
            type=str,
            default=None,
            help=_("local path to use instead of or alongside remote"),
        )
        p.add_argument(
            "--name", type=str, default=None, help=_("human-readable name for the repo")
        )

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
            logger.F(_("invalid repo id '{id}'").format(id=repo_id))
            return 1

        if repo_id == DEFAULT_REPO_ID:
            logger.F(
                _(
                    "'{id}' is reserved; use [repo] config to configure the default repository"
                ).format(
                    id=DEFAULT_REPO_ID,
                )
            )
            return 1

        if not url and not local:
            logger.F(_("at least one of URL or --local must be provided"))
            return 1

        if local and not pathlib.Path(local).is_absolute():
            logger.F(_("local path '{path}' must be absolute").format(path=local))
            return 1

        # Check for conflict with existing entries.
        for entry in cfg.repo_entries:
            if entry.id == repo_id:
                logger.F(_("a repo with id '{id}' already exists").format(id=repo_id))
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

        logger.I(_("repo '{id}' added; run 'ruyi update' to sync").format(id=repo_id))
        return 0


class RepoRemoveCommand(
    RepoCommand,
    cmd="remove",
    help=_("Remove a package repository"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument("id", type=str, help=_("repository identifier to remove"))
        if gc.is_cli_autocomplete:
            from .cli_completion import repo_id_completer_builder

            a.completer = repo_id_completer_builder(gc)
        p.add_argument(
            "--purge",
            action="store_true",
            default=False,
            help=_("also remove cached repo data from disk"),
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        import shutil

        from ..config.editor import ConfigEditor
        from .repo import DEFAULT_REPO_ID

        logger = cfg.logger
        repo_id: str = args.id

        if repo_id == DEFAULT_REPO_ID:
            logger.F(
                _(
                    "cannot remove the default repo '{id}'; use 'repo disable' instead"
                ).format(
                    id=DEFAULT_REPO_ID,
                )
            )
            return 1

        # Check if entry is system-provided
        for entry in cfg.repo_entries:
            if entry.id == repo_id and entry.is_system:
                logger.F(
                    _(
                        "cannot remove system-provided repo '{id}'; use 'repo disable' instead"
                    ).format(
                        id=repo_id,
                    )
                )
                return 1

        with ConfigEditor.work_on_user_local_config(cfg) as editor:
            if not editor.remove_repos_entry(repo_id):
                logger.F(
                    _("no repo with id '{id}' found in user config").format(id=repo_id)
                )
                return 1
            editor.stage()

        if args.purge:
            repo_dir = cfg.get_repo_dir_for_id(repo_id)
            if pathlib.Path(repo_dir).exists():
                shutil.rmtree(repo_dir)
                logger.I(_("purged cached data at '{path}'").format(path=repo_dir))

        logger.I(_("repo '{id}' removed").format(id=repo_id))
        return 0


class RepoEnableCommand(
    RepoCommand,
    cmd="enable",
    help=_("Enable a package repository"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument("id", type=str, help=_("repository identifier to enable"))
        if gc.is_cli_autocomplete:
            from .cli_completion import repo_id_completer_builder

            a.completer = repo_id_completer_builder(gc)

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor
        from ..config.schema import KEY_REPOS_ACTIVE

        logger = cfg.logger
        repo_id: str = args.id

        with ConfigEditor.work_on_user_local_config(cfg) as editor:
            if not editor.update_repos_entry(repo_id, {KEY_REPOS_ACTIVE: True}):
                logger.F(
                    _("no repo with id '{id}' found in user config").format(id=repo_id)
                )
                return 1
            editor.stage()

        logger.I(_("repo '{id}' enabled").format(id=repo_id))
        return 0


class RepoDisableCommand(
    RepoCommand,
    cmd="disable",
    help=_("Disable a package repository"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument("id", type=str, help=_("repository identifier to disable"))
        if gc.is_cli_autocomplete:
            from .cli_completion import repo_id_completer_builder

            a.completer = repo_id_completer_builder(gc)

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor
        from ..config.schema import KEY_REPOS_ACTIVE

        logger = cfg.logger
        repo_id: str = args.id

        with ConfigEditor.work_on_user_local_config(cfg) as editor:
            if not editor.update_repos_entry(repo_id, {KEY_REPOS_ACTIVE: False}):
                logger.F(
                    _("no repo with id '{id}' found in user config").format(id=repo_id)
                )
                return 1
            editor.stage()

        logger.I(_("repo '{id}' disabled").format(id=repo_id))
        return 0


class RepoSetPriorityCommand(
    RepoCommand,
    cmd="set-priority",
    help=_("Set the priority of a package repository"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument("id", type=str, help=_("repository identifier"))
        if gc.is_cli_autocomplete:
            from .cli_completion import repo_id_completer_builder

            a.completer = repo_id_completer_builder(gc)
        p.add_argument("priority", type=int, help=_("new priority value"))

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor
        from ..config.schema import KEY_REPOS_PRIORITY

        logger = cfg.logger
        repo_id: str = args.id
        priority: int = args.priority

        with ConfigEditor.work_on_user_local_config(cfg) as editor:
            if not editor.update_repos_entry(repo_id, {KEY_REPOS_PRIORITY: priority}):
                logger.F(
                    _("no repo with id '{id}' found in user config").format(id=repo_id)
                )
                return 1
            editor.stage()

        logger.I(
            _("repo '{id}' priority set to {priority}").format(
                id=repo_id, priority=priority
            )
        )
        return 0
