import argparse

from .. import log
from ..config import GlobalConfig
from .repo import MetadataRepo


def cli_list_profiles(config: GlobalConfig, args: argparse.Namespace) -> int:
    mr = MetadataRepo(config)

    for arch in mr.get_supported_arches():
        for p in mr.iter_profiles_for_arch(arch):
            if not p.need_flavor:
                log.stdout(p.id)
                continue

            log.stdout(f"{p.id} (needs flavor(s): {p.need_flavor})")

    return 0
