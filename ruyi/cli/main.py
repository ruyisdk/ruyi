import atexit
import os
import sys
from typing import Final

from ..config import GlobalConfig
from . import RUYI_ENTRYPOINT_NAME

ALLOWED_RUYI_ENTRYPOINT_NAMES: Final = (
    RUYI_ENTRYPOINT_NAME,
    f"{RUYI_ENTRYPOINT_NAME}.exe",
    f"{RUYI_ENTRYPOINT_NAME}.bin",  # Nuitka one-file program cache
    "__main__.py",
)


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0).lower() in ALLOWED_RUYI_ENTRYPOINT_NAMES


def main(argv: list[str]) -> int:
    gc = GlobalConfig.load_from_config()
    if gc.telemetry is not None:
        gc.telemetry.init_installation(False)
        atexit.register(gc.telemetry.flush)

    if not is_called_as_ruyi(argv[0]):
        from ..mux.runtime import mux_main

        # record an invocation and the command name being proxied to
        if gc.telemetry is not None:
            target = os.path.basename(argv[0])
            gc.telemetry.record("cli:mux-invocation-v1", target=target)

        return mux_main(argv)

    import ruyi
    from .. import log
    from .cmd import CLIEntrypoint, RootCommand
    from . import builtin_commands

    del builtin_commands

    p = RootCommand.build_argparse()
    args = p.parse_args(argv[1:])
    ruyi.set_porcelain(args.porcelain)

    nuitka_info = "not compiled"
    if hasattr(ruyi, "__compiled__"):
        nuitka_info = f"__compiled__ = {ruyi.__compiled__}"

    log.D(
        f"__main__.__file__ = {ruyi.main_file()}, sys.executable = {sys.executable}, {nuitka_info}"
    )
    log.D(f"argv[0] = {argv[0]}, self_exe = {ruyi.self_exe()}")
    log.D(f"args={args}")

    func: CLIEntrypoint = args.func

    # record every invocation's subcommand for better insight into usage
    # frequencies
    try:
        telemetry_key = args.tele_key
    except AttributeError:
        log.F("internal error: CLI entrypoint was added without a telemetry key")
        return 1

    if gc.telemetry is not None:
        gc.telemetry.print_telemetry_notice()
        gc.telemetry.record("cli:invocation-v1", key=telemetry_key)

    return func(gc, args)
