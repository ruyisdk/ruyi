import argparse

from ..config import RuyiConfig
from .repo import MetadataRepo


def cli_update(args: argparse.Namespace) -> int:
    config = RuyiConfig.load_from_config()
    mr = MetadataRepo(
        config.get_repo_dir(), config.get_repo_url(), config.get_repo_branch()
    )
    mr.sync()
    return 0
