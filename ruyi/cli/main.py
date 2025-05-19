import atexit
import os
import sys
from typing import Final

from ..config import GlobalConfig
from ..telemetry import TelemetryScope
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
    if gc.telemetry is not None:
        gc.telemetry.check_first_run_status()
        gc.telemetry.init_installation(False)
        atexit.register(gc.telemetry.flush)
        gc.telemetry.maybe_prompt_for_first_run_upload()

    if not is_called_as_ruyi(argv[0]):
        from ..mux.runtime import mux_main

        # record an invocation and the command name being proxied to
        if gc.telemetry is not None:
            target = os.path.basename(argv[0])
            gc.telemetry.record(
                TelemetryScope(None),
                "cli:mux-invocation-v1",
                target=target,
            )

        return mux_main(gm, gc, argv)

    import ruyi
    from .cmd import CLIEntrypoint, RootCommand
    from . import builtin_commands

    del builtin_commands

    logger = gc.logger
    p = RootCommand.build_argparse(gc)
    args = p.parse_args(argv[1:])
    gm.is_porcelain = args.porcelain

    nuitka_info = "not compiled"
    if hasattr(ruyi, "__compiled__"):
        nuitka_info = f"__compiled__ = {ruyi.__compiled__}"

    logger.D(
        f"__main__.__file__ = {gm.main_file}, sys.executable = {sys.executable}, {nuitka_info}"
    )
    logger.D(f"argv[0] = {gm.argv0}, self_exe = {gm.self_exe}")
    logger.D(f"args={args}")

    func: CLIEntrypoint = args.func

    # record every invocation's subcommand for better insight into usage
    # frequencies
    try:
        telemetry_key = args.tele_key
    except AttributeError:
        logger.F("internal error: CLI entrypoint was added without a telemetry key")
        return 1

    if gc.telemetry is not None:
        gc.telemetry.print_telemetry_notice()
        gc.telemetry.record(
            TelemetryScope(None),
            "cli:invocation-v1",
            key=telemetry_key,
        )

    return func(gc, args)
