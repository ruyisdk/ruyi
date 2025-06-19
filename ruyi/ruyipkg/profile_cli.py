import argparse

from ..config import GlobalConfig
from .list_cli import ListCommand


class ListProfilesCommand(
    ListCommand,
    cmd="profiles",
    help="List all available profiles",
):
    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        logger = cfg.logger
        mr = cfg.repo

        for arch in mr.get_supported_arches():
            for p in mr.iter_profiles_for_arch(arch):
                if not p.need_quirks:
                    logger.stdout(p.id)
                    continue

                logger.stdout(f"{p.id} (needs quirks: {p.need_quirks})")

        return 0
