import argparse

from .. import config
from ..config.schema import encode_value
from .. import log
from .cmd import RootCommand


# Config management commands
class ConfigCommand(
    RootCommand,
    cmd="config",
    has_subcommands=True,
    help="Manage Ruyi's config options",
):
    pass


class ConfigGetCommand(
    ConfigCommand,
    cmd="get",
    help="Query the value of a Ruyi config option",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "key",
            type=str,
            help="The Ruyi config option to query",
        )

    @classmethod
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
        key: str = args.key

        val = cfg.get_by_key(key)
        if val is None:
            return 1

        log.stdout(encode_value(val))
        return 0
