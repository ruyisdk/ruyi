import argparse
from typing import TYPE_CHECKING

from ..i18n import _
from .list_cli import ListCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class ListProfilesCommand(
    ListCommand,
    cmd="profiles",
    help=_("List all available profiles"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .profile import do_list_profiles_porcelain

        logger = cfg.logger
        mr = cfg.repo

        if cfg.is_porcelain:
            return do_list_profiles_porcelain(mr)

        for arch in mr.get_supported_arches():
            for p in mr.iter_profiles_for_arch(arch):
                if not p.need_quirks:
                    logger.stdout(p.id)
                    continue

                logger.stdout(
                    _("{profile_id} (needs quirks: {need_quirks})").format(
                        profile_id=p.id,
                        need_quirks=p.need_quirks,
                    )
                )

        return 0
