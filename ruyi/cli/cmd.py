import argparse
from typing import Callable, IO, Protocol, TYPE_CHECKING

from . import RUYI_ENTRYPOINT_NAME

if TYPE_CHECKING:
    from ..config import GlobalConfig
    from .completion import ArgumentParser

    CLIEntrypoint = Callable[["GlobalConfig", argparse.Namespace], int]


class _PrintHelp(Protocol):
    def print_help(self, file: IO[str] | None = None) -> None: ...


def _wrap_help(x: _PrintHelp) -> "CLIEntrypoint":
    def _wrapped_(gc: "GlobalConfig", args: argparse.Namespace) -> int:
        x.print_help()
        return 0

    return _wrapped_


class BaseCommand:
    parsers: "list[type[BaseCommand]]" = []

    cmd: str | None
    _tele_key: str | None
    has_subcommands: bool
    is_experimental: bool
    is_subcommand_required: bool
    has_main: bool
    aliases: list[str]
    description: str | None
    prog: str | None
    help: str | None

    def __init_subclass__(
        cls,
        cmd: str | None,
        has_subcommands: bool = False,
        is_subcommand_required: bool = False,
        is_experimental: bool = False,
        has_main: bool | None = None,
        aliases: list[str] | None = None,
        description: str | None = None,
        prog: str | None = None,
        help: str | None = None,
        **kwargs: object,
    ) -> None:
        cls.cmd = cmd

        if cmd is None:
            cls._tele_key = None
        else:
            parent_cls = cls.mro()[1]
            parent_raw_tele_key = getattr(parent_cls, "_tele_key", None)
            if parent_raw_tele_key is None:
                cls._tele_key = cmd
            else:
                cls._tele_key = f"{parent_raw_tele_key} {cmd}"

        cls.has_subcommands = has_subcommands
        cls.is_subcommand_required = is_subcommand_required
        cls.is_experimental = is_experimental
        cls.has_main = has_main if has_main is not None else not has_subcommands

        # argparse params
        cls.aliases = aliases or []
        cls.description = description
        cls.prog = prog
        cls.help = help

        cls.parsers.append(cls)

        super().__init_subclass__(**kwargs)

    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        """Configure arguments for this parser."""
        pass

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        """Entrypoint of this command."""
        raise NotImplementedError

    @classmethod
    def is_root(cls) -> bool:
        return cls.cmd is None

    @classmethod
    def _build_tele_key(cls) -> str:
        return "<bare>" if cls._tele_key is None else cls._tele_key

    @classmethod
    def build_argparse(cls, gc: "GlobalConfig") -> "ArgumentParser":
        from .completion import ArgumentParser

        p = ArgumentParser(prog=cls.prog, description=cls.description)
        cls.configure_args(gc, p)
        cls._populate_defaults(p)
        cls._maybe_build_subcommands(gc, p)
        return p

    @classmethod
    def _maybe_build_subcommands(
        cls,
        gc: "GlobalConfig",
        p: "ArgumentParser",
    ) -> None:
        if not cls.has_subcommands:
            return

        sp = p.add_subparsers(
            title="subcommands",
            required=cls.is_subcommand_required,
        )
        for subcmd_cls in cls.parsers:
            if subcmd_cls.mro()[1] is not cls:
                # do not recurse onto self or non-direct subclasses
                continue
            if subcmd_cls.is_experimental and not gc.is_experimental:
                # skip configuring experimental commands if not enabled in
                # the environment
                continue
            subcmd_cls._configure_subcommand(gc, sp)

    @classmethod
    def _configure_subcommand(
        cls,
        gc: "GlobalConfig",
        sp: "argparse._SubParsersAction[ArgumentParser]",
    ) -> argparse.ArgumentParser:
        assert cls.cmd is not None
        p = sp.add_parser(
            cls.cmd,
            aliases=cls.aliases,
            help=cls.help,
        )
        cls.configure_args(gc, p)
        cls._populate_defaults(p)
        cls._maybe_build_subcommands(gc, p)
        return p

    @classmethod
    def _populate_defaults(cls, p: "ArgumentParser") -> None:
        if cls.has_main:
            p.set_defaults(func=cls.main, tele_key=cls._build_tele_key())
        else:
            p.set_defaults(func=_wrap_help(p), tele_key=cls._build_tele_key())


class RootCommand(
    BaseCommand,
    cmd=None,
    has_subcommands=True,
    has_main=True,
    prog=RUYI_ENTRYPOINT_NAME,
    description="RuyiSDK Package Manager",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        from .version_cli import cli_version

        p.add_argument(
            "-V",
            "--version",
            action="store_const",
            dest="func",
            const=cli_version,
            help="Print version information",
        )
        p.add_argument(
            "--porcelain",
            action="store_true",
            help="Give the output in a machine-friendly format if applicable",
        )

        # https://github.com/python/cpython/issues/67037 prevents the registration
        # of undocumented subcommands, so a preferred usage of
        # "ruyi completion-script --shell=bash" is not possible right now.
        p.add_argument(
            "--output-completion-script",
            action="store",
            type=str,
            dest="completion_script",
            default=None,
            help=argparse.SUPPRESS,
        )

    @classmethod
    def main(cls, cfg: "GlobalConfig", args: argparse.Namespace) -> int:
        sh: str | None = args.completion_script
        if not sh:
            args._parser.print_help()  # pylint: disable=protected-access
            return 0
        # the rest are implementation of "--output-completion-script"

        from .completion import SUPPORTED_SHELLS

        if sh not in SUPPORTED_SHELLS:
            raise ValueError(f"Unsupported shell: {sh}")

        import sys
        from ..resource_bundle import get_resource_str

        script = get_resource_str("_ruyi_completion")
        assert script is not None, "should never happen; completion script not found"
        sys.stdout.write(script)
        return 0


# Repo admin commands
class AdminCommand(
    RootCommand,
    cmd="admin",
    has_subcommands=True,
    # https://github.com/python/cpython/issues/67037
    # help=argparse.SUPPRESS,
    help="(NOT FOR REGULAR USERS) Subcommands for managing Ruyi repos",
):
    @classmethod
    def configure_args(cls, gc: "GlobalConfig", p: "ArgumentParser") -> None:
        pass
