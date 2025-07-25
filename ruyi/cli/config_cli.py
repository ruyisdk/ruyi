import argparse
from typing import TYPE_CHECKING

from .cmd import RootCommand

if TYPE_CHECKING:
    from .completion import ArgumentParser
    from .. import config


# Config management commands
class ConfigCommand(
    RootCommand,
    cmd="config",
    has_subcommands=True,
    help="Manage Ruyi's config options",
):
    @classmethod
    def configure_args(
        cls,
        gc: "config.GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        pass


class ConfigGetCommand(
    ConfigCommand,
    cmd="get",
    help="Query the value of a Ruyi config option",
):
    @classmethod
    def configure_args(
        cls,
        gc: "config.GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        p.add_argument(
            "key",
            type=str,
            help="The Ruyi config option to query",
        )

    @classmethod
    def main(cls, cfg: "config.GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.schema import encode_value

        key: str = args.key

        val = cfg.get_by_key(key)
        if val is None:
            return 1

        cfg.logger.stdout(encode_value(val))
        return 0


class ConfigSetCommand(
    ConfigCommand,
    cmd="set",
    help="Set the value of a Ruyi config option",
):
    @classmethod
    def configure_args(
        cls,
        gc: "config.GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        p.add_argument(
            "key",
            type=str,
            help="The Ruyi config option to set",
        )
        p.add_argument(
            "value",
            type=str,
            help="The value to set the option to",
        )

    @classmethod
    def main(cls, cfg: "config.GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor
        from ..config.schema import decode_value

        key: str = args.key
        val: str = args.value

        pyval = decode_value(key, val)
        with ConfigEditor.work_on_user_local_config(cfg) as ed:
            ed.set_value(key, pyval)
            ed.stage()

        return 0


class ConfigUnsetCommand(
    ConfigCommand,
    cmd="unset",
    help="Unset a Ruyi config option",
):
    @classmethod
    def configure_args(
        cls,
        gc: "config.GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        p.add_argument(
            "key",
            type=str,
            help="The Ruyi config option to unset",
        )

    @classmethod
    def main(cls, cfg: "config.GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor

        key: str = args.key

        with ConfigEditor.work_on_user_local_config(cfg) as ed:
            ed.unset_value(key)
            ed.stage()

        return 0


class ConfigRemoveSectionCommand(
    ConfigCommand,
    cmd="remove-section",
    help="Remove a section from the Ruyi config",
):
    @classmethod
    def configure_args(
        cls,
        gc: "config.GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        p.add_argument(
            "section",
            type=str,
            help="The section to remove",
        )

    @classmethod
    def main(cls, cfg: "config.GlobalConfig", args: argparse.Namespace) -> int:
        from ..config.editor import ConfigEditor

        section: str = args.section

        with ConfigEditor.work_on_user_local_config(cfg) as ed:
            ed.remove_section(section)
            ed.stage()

        return 0
