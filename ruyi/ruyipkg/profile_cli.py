import argparse

from .. import log
from ..config import RuyiConfig
from .repo import MetadataRepo


def cli_list_profiles(args: argparse.Namespace) -> int:
    config = RuyiConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )

    for p in mr.iter_profiles():
        if not p.need_flavor:
            log.stdout(p.name)
            continue

        log.stdout(f"{p.name} (needs flavor(s): {p.need_flavor})")

    return 0
