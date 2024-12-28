import argparse
import datetime

from .. import config
from ..config.editor import ConfigEditor
from ..config import schema
from .. import log
from ..cli.cmd import RootCommand


# Telemetry preference commands
class TelemetryCommand(
    RootCommand,
    cmd="telemetry",
    has_subcommands=True,
    help="Manage your telemetry preferences",
):
    pass


class TelemetryConsentCommand(
    TelemetryCommand,
    cmd="consent",
    aliases=["on"],
    help="Give consent to telemetry data uploads",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
        now = datetime.datetime.now().astimezone()
        with ConfigEditor.work_on_user_local_config(cfg) as ed:
            ed.set_value((schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_MODE), "on")
            ed.set_value(
                (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_UPLOAD_CONSENT), now
            )
            ed.stage()

        log.I("telemetry data uploading is now enabled")
        log.I("you can opt out at any time by running [yellow]ruyi telemetry optout[/]")

        return 0


class TelemetryLocalCommand(
    TelemetryCommand,
    cmd="local",
    help="Set telemetry mode to local collection only",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
        with ConfigEditor.work_on_user_local_config(cfg) as ed:
            ed.set_value((schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_MODE), "local")
            ed.unset_value(
                (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_UPLOAD_CONSENT)
            )
            ed.stage()

        log.I("telemetry mode is now set to local collection only")
        log.I(
            "you can re-enable telemetry data uploading at any time by running [yellow]ruyi telemetry consent[/]"
        )
        log.I("or opt out at any time by running [yellow]ruyi telemetry optout[/]")

        return 0


class TelemetryOptoutCommand(
    TelemetryCommand,
    cmd="optout",
    aliases=["off"],
    help="Opt out of telemetry data collection",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
        with ConfigEditor.work_on_user_local_config(cfg) as ed:
            ed.set_value((schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_MODE), "off")
            ed.unset_value(
                (schema.SECTION_TELEMETRY, schema.KEY_TELEMETRY_UPLOAD_CONSENT)
            )
            ed.stage()

        log.I("telemetry data collection is now disabled")
        log.I(
            "you can re-enable telemetry data uploads at any time by running [yellow]ruyi telemetry consent[/]"
        )

        return 0


class TelemetryStatusCommand(
    TelemetryCommand,
    cmd="status",
    help="Print the current telemetry mode",
):
    @classmethod
    def configure_args(cls, p: argparse.ArgumentParser) -> None:
        pass

    @classmethod
    def main(cls, cfg: config.GlobalConfig, args: argparse.Namespace) -> int:
        log.stdout(cfg.telemetry_mode)
        return 0
