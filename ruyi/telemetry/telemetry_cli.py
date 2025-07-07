import argparse
import datetime
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


# Telemetry preference commands
class TelemetryCommand(
    RootCommand,
    cmd="telemetry",
    has_subcommands=True,
    help="Manage your telemetry preferences",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass


class TelemetryConsentCommand(
    TelemetryCommand,
    cmd="consent",
    aliases=["on"],
    help="Give consent to telemetry data uploads",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .provider import set_telemetry_mode

        now = datetime.datetime.now().astimezone()
        set_telemetry_mode(cfg, "on", now)
        return 0


class TelemetryLocalCommand(
    TelemetryCommand,
    cmd="local",
    help="Set telemetry mode to local collection only",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .provider import set_telemetry_mode

        set_telemetry_mode(cfg, "local")
        return 0


class TelemetryOptoutCommand(
    TelemetryCommand,
    cmd="optout",
    aliases=["off"],
    help="Opt out of telemetry data collection",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        from .provider import set_telemetry_mode

        set_telemetry_mode(cfg, "off")
        return 0


class TelemetryStatusCommand(
    TelemetryCommand,
    cmd="status",
    help="Print the current telemetry mode",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output",
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        verbose: bool = args.verbose
        if not verbose:
            cfg.logger.stdout(cfg.telemetry_mode)
            return 0

        if cfg.telemetry is None:
            cfg.logger.I(
                "telemetry mode is [green]off[/]: no further data will be collected"
            )
            return 0

        cfg.telemetry.print_telemetry_notice(for_cli_verbose_output=True)
        return 0


class TelemetryUploadCommand(
    TelemetryCommand,
    cmd="upload",
    help="Upload collected telemetry data now",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        if cfg.telemetry is None:
            cfg.logger.W("telemetry is disabled, nothing to upload")
            return 0

        cfg.telemetry.flush(upload_now=True)
        # disable the flush at program exit because we have just done that
        cfg.telemetry.discard_events()
        return 0
