import argparse
import datetime
from typing import TYPE_CHECKING

from ..cli.cmd import RootCommand
from ..i18n import _

if TYPE_CHECKING:
    from ..cli.completion import ArgumentParser
    from ..config import GlobalConfig


# Telemetry preference commands
class TelemetryCommand(
    RootCommand,
    cmd="telemetry",
    has_main=True,
    has_subcommands=True,
    help=_("Manage your telemetry preferences"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        # https://github.com/python/cpython/issues/67037 prevents the registration
        # of undocumented subcommands, so a preferred usage of
        # "ruyi telemetry cron-upload" is not possible right now.
        p.add_argument(
            "--cron-upload",
            action="store_true",
            dest="cron_upload",
            default=False,
            help=argparse.SUPPRESS,
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        cron_upload: bool = args.cron_upload
        if not cron_upload:
            args._parser.print_help()  # pylint: disable=protected-access
            return 0

        # the rest are implementation of "--cron-upload"

        cfg.telemetry.flush(cron_mode=True)
        return 0


class TelemetryConsentCommand(
    TelemetryCommand,
    cmd="consent",
    aliases=["on"],
    help=_("Give consent to telemetry data uploads"),
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
    help=_("Set telemetry mode to local collection only"),
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
    help=_("Opt out of telemetry data collection"),
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
    help=_("Print the current telemetry mode"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        p.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help=_("Enable verbose output"),
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        verbose: bool = args.verbose
        if not verbose:
            cfg.logger.stdout(cfg.telemetry_mode)
            return 0

        if cfg.telemetry is None:
            cfg.logger.I(
                _("telemetry mode is [green]off[/]: no further data will be collected")
            )
            return 0

        cfg.telemetry.print_telemetry_notice(for_cli_verbose_output=True)
        return 0


class TelemetryUploadCommand(
    TelemetryCommand,
    cmd="upload",
    help=_("Upload collected telemetry data now"),
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        cfg.telemetry.flush(upload_now=True)
        # disable the flush at program exit because we have just done that
        cfg.telemetry.discard_events()
        return 0
