import atexit
import os
import sys
from typing import Final, TYPE_CHECKING

from ..config import GlobalConfig
from ..telemetry.scope import TelemetryScope
from ..utils.global_mode import GlobalModeProvider
from . import RUYI_ENTRYPOINT_NAME

ALLOWED_RUYI_ENTRYPOINT_NAMES: Final = (
    RUYI_ENTRYPOINT_NAME,
    f"{RUYI_ENTRYPOINT_NAME}.exe",
    f"{RUYI_ENTRYPOINT_NAME}.bin",  # Nuitka one-file program cache
    "__main__.py",
)


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0).lower() in ALLOWED_RUYI_ENTRYPOINT_NAMES


def main(gm: GlobalModeProvider, gc: GlobalConfig, argv: list[str]) -> int:
    if tm := gc.telemetry:
        tm.check_first_run_status()
        tm.init_installation(False)
        atexit.register(tm.flush)
        tm.maybe_prompt_for_first_run_upload()

    if not is_called_as_ruyi(gm.argv0):
        from ..mux.runtime import mux_main

        # record an invocation and the command name being proxied to
        if tm := gc.telemetry:
            tm.record(
                TelemetryScope(None),
                "cli:mux-invocation-v1",
                target=os.path.basename(gm.argv0),
            )

        return mux_main(gm, gc, argv)

    import ruyi
    from .cmd import RootCommand
    from . import builtin_commands

    del builtin_commands

    if TYPE_CHECKING:
        from .cmd import CLIEntrypoint

    logger = gc.logger
    p = RootCommand.build_argparse(gc)

    # We have to ensure argcomplete is only requested when it's supposed to,
    # as the argcomplete import is very costly in terms of startup time, and
    # that the package name completer requires the whole repo to be synced
    # (which may not be the case for an out-of-the-box experience).
    if gm.is_cli_autocomplete:
        import argcomplete
        from .completer import NoneCompleter

        argcomplete.autocomplete(
            p,
            always_complete_options=True,
            default_completer=NoneCompleter(),
        )

    args = p.parse_args(argv[1:])
    # for getting access to the argparse parser in the CLI entrypoint
    args._parser = p  # pylint: disable=protected-access

    gm.is_porcelain = args.porcelain

    nuitka_info = "not compiled"
    if hasattr(ruyi, "__compiled__"):
        nuitka_info = f"__compiled__ = {ruyi.__compiled__}"

    logger.D(
        f"__main__.__file__ = {gm.main_file}, sys.executable = {sys.executable}, {nuitka_info}"
    )
    logger.D(f"argv[0] = {gm.argv0}, self_exe = {gm.self_exe}")
    logger.D(f"args={args}")

    func: "CLIEntrypoint" = args.func

    # record every invocation's subcommand for better insight into usage
    # frequencies
    try:
        telemetry_key: str = args.tele_key
    except AttributeError:
        logger.F("internal error: CLI entrypoint was added without a telemetry key")
        return 1

    # Special-case the `--output-completion-script` argument; treat it as if
    # "ruyi completion-script" were called.
    try:
        if args.completion_script:
            telemetry_key = "completion-script"
    except AttributeError:
        pass

    if tm := gc.telemetry:
        tm.print_telemetry_notice()
        tm.record(
            TelemetryScope(None),
            "cli:invocation-v1",
            key=telemetry_key,
        )

    return func(gc, args)
