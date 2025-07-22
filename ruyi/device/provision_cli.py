import argparse
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


class DeviceCommand(
    RootCommand,
    cmd="device",
    has_subcommands=True,
    help="Manage devices",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass


class DeviceProvisionCommand(
    DeviceCommand,
    cmd="provision",
    aliases=["flash"],
    help="Interactively initialize a device for development",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .provision import do_provision_interactive

        try:
            return do_provision_interactive(cfg)
        except KeyboardInterrupt:
            cfg.logger.stdout("\n\nKeyboard interrupt received, exiting.", end="\n\n")
            return 1
