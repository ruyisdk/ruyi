import argparse

from .. import log
from ..config import GlobalConfig
from .repo import MetadataRepo


def cli_list_profiles(args: argparse.Namespace) -> int:
    config = GlobalConfig.load_from_config()
    mr = MetadataRepo(config)

    for p in mr.iter_profiles():
        if not p.need_flavor:
            log.stdout(p.name)
            continue

        log.stdout(f"{p.name} (needs flavor(s): {p.need_flavor})")

    return 0
