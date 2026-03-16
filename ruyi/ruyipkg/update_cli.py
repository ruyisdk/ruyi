import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand
from ..i18n import _

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class UpdateCommand(
    RootCommand,
    cmd="update",
    help=_("Update RuyiSDK repo and packages"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        a = p.add_argument(
            "--repo",
            type=str,
            default=None,
            help=_("only sync the repo with this ID"),
        )
        if gc.is_cli_autocomplete:
            from .cli_completion import repo_id_completer_builder

            a.completer = repo_id_completer_builder(gc)

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from . import news
        from .state import BoundInstallationStateStore

        logger = cfg.logger
        mr = cfg.repo

        repo_id: str | None = args.repo
        if repo_id is not None:
            try:
                mr.sync_one(repo_id)
            except ValueError:
                logger.F(_("no active repo with id '{id}'").format(id=repo_id))
                return 1
        else:
            mr.sync_all()

        # check for upgradable packages
        bis = BoundInstallationStateStore(cfg.ruyipkg_global_state, mr)
        upgradable = list(bis.iter_upgradable_pkgs(cfg.include_prereleases))

        if upgradable:
            logger.stdout(
                _(
                    "\nNewer versions are available for some of your installed packages:\n"
                )
            )
            for pm, new_ver, migrated in upgradable:
                logger.stdout(
                    f"  - [bold]{pm.category}/{pm.name}[/]: [yellow]{pm.ver}[/] -> [green]{new_ver}[/]"
                )
                if migrated:
                    logger.W(
                        _(
                            "package '{category}/{name}' was installed from "
                            "repo '{repo}' but the latest version is in a "
                            "different repo"
                        ).format(
                            category=pm.category,
                            name=pm.name,
                            repo=pm.repo_id,
                        )
                    )
            logger.stdout(
                _(
                    """
Re-run [yellow]ruyi install[/] to upgrade, and don't forget to re-create any affected
virtual environments."""
                )
            )

        news.maybe_notify_unread_news(cfg, False)

        return 0
