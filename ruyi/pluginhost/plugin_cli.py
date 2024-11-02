import argparse

from ..cli.cmd import AdminCommand
from ..config import GlobalConfig
from ..ruyipkg.repo import MetadataRepo


class AdminRunPluginCommand(
    AdminCommand,
    cmd="run-plugin-cmd",
    help="Run a plugin-defined command",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "cmd_name",
            type=str,
            metavar="COMMAND-NAME",
            help="Command name",
        )
        p.add_argument(
            "cmd_args",
            type=str,
            nargs="*",
            metavar="COMMAND-ARG",
            help="Arguments to pass to the plugin command",
        )

    @classmethod
    def main(cls, cfg: GlobalConfig, args: argparse.Namespace) -> int:
        cmd_name = args.cmd_name
        cmd_args = args.cmd_args

        mr = MetadataRepo(cfg)
        return mr.run_plugin_cmd(cmd_name, cmd_args)
