import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import AdminCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class AdminRunPluginCommand(
    AdminCommand,
    cmd="run-plugin-cmd",
    help="Run a plugin-defined command",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
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
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        cmd_name = args.cmd_name
        cmd_args = args.cmd_args

        return cfg.repo.run_plugin_cmd(cmd_name, cmd_args)
