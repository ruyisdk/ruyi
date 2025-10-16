import atexit
import os
import sys
from typing import Final, TYPE_CHECKING

from ..config import GlobalConfig
from ..telemetry.scope import TelemetryScope
from ..utils.global_mode import GlobalModeProvider
from ..version import RUYI_SEMVER
from . import RUYI_ENTRYPOINT_NAME
from .oobe import OOBE

ALLOWED_RUYI_ENTRYPOINT_NAMES: Final = (
    RUYI_ENTRYPOINT_NAME,
    f"{RUYI_ENTRYPOINT_NAME}.exe",
    f"{RUYI_ENTRYPOINT_NAME}.bin",  # Nuitka one-file program cache
    "__main__.py",
)


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0).lower() in ALLOWED_RUYI_ENTRYPOINT_NAMES


def should_prompt_for_renaming(argv0: str) -> bool:
    # We need to allow things like "ruyi-qemu" through, to not break our mux.
    # Only consider filenames starting with both our name *and* version to be
    # un-renamed onefile artifacts that warrant a rename prompt.
    likely_artifact_name_prefix = f"{RUYI_ENTRYPOINT_NAME}-{RUYI_SEMVER}."
    return os.path.basename(argv0).lower().startswith(likely_artifact_name_prefix)


def main(gm: GlobalModeProvider, gc: GlobalConfig, argv: list[str]) -> int:
    logger = gc.logger

    # do not init telemetry or OOBE on CLI auto-completion invocations, because
    # our output isn't meant for humans in that case, and a "real" invocation
    # will likely follow shortly after
    if not gm.is_cli_autocomplete:
        oobe = OOBE(gc)

        if tm := gc.telemetry:
            tm.check_first_run_status()
            tm.init_installation(False)
            atexit.register(tm.flush)
            oobe.handlers.append(tm.oobe_prompt)

        oobe.maybe_prompt()

    if not is_called_as_ruyi(gm.argv0):
        if should_prompt_for_renaming(gm.argv0):
            logger.F(
                f"the {RUYI_ENTRYPOINT_NAME} executable must be named [green]'{RUYI_ENTRYPOINT_NAME}'[/] to work"
            )
            logger.I(f"it is now [yellow]'{gm.argv0}'[/]")
            logger.I("please rename the command file and retry")
            return 1

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
