import argparse

from ..config import GlobalConfig
from .pkg_cli import ListCommand


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
                if not p.need_flavor:
                    logger.stdout(p.id)
                    continue

                logger.stdout(f"{p.id} (needs flavor(s): {p.need_flavor})")

        return 0
