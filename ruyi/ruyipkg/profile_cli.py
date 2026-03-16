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
        logger = cfg.logger
        mr = cfg.repo

        for arch in mr.get_supported_arches():
            for p in mr.iter_profiles_for_arch(arch):
                if not p.need_quirks:
                    logger.stdout(
                        _("{profile_id} (arch: [green]{arch}[/])").format(
                            profile_id=p.id,
                            arch=arch,
                        )
                    )
                    continue

                logger.stdout(
                    _(
                        "{profile_id} (arch: [green]{arch}[/], needs quirks: [yellow]{need_quirks}[/])"
                    ).format(
                        profile_id=p.id,
                        arch=arch,
                        need_quirks=", ".join(p.need_quirks),
                    )
                )

        return 0
