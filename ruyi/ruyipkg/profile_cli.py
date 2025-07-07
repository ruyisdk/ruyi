import argparse
from typing import TYPE_CHECKING

from .list_cli import ListCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class ListProfilesCommand(
    ListCommand,
    cmd="profiles",
    help="List all available profiles",
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
                    logger.stdout(p.id)
                    continue

                logger.stdout(f"{p.id} (needs quirks: {p.need_quirks})")

        return 0
