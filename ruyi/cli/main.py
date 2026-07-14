import atexit
import os
import sys
from typing import Final, TYPE_CHECKING

from ..config import GlobalConfig
from ..i18n import _
from ..telemetry.scope import TelemetryScope
from ..utils.global_mode import (
    GlobalModeProvider,
    is_cli_completion_script_requested,
)
from ..version import RUYI_SEMVER
from . import RUYI_ENTRYPOINT_NAME
from .oobe import OOBE

ALLOWED_RUYI_ENTRYPOINT_NAMES: Final = (
    RUYI_ENTRYPOINT_NAME,
    f"{RUYI_ENTRYPOINT_NAME}.exe",
    f"{RUYI_ENTRYPOINT_NAME}.bin",  # Nuitka one-file program cache
    "__main__.py",
    # Undocumented: for testing purposes only, to allow multiple versions of
    # ruyi to peacefully co-exist, while not allowing conflating the different
    # versions.
    f"{RUYI_ENTRYPOINT_NAME}-{RUYI_SEMVER}",
    f"{RUYI_ENTRYPOINT_NAME}-{RUYI_SEMVER}.exe",
)
VERSION_QUERY_FLAGS: Final = frozenset(("-V", "--version"))
VERSION_QUERY_SUBCOMMAND: Final = "version"


def is_called_as_ruyi(argv0: str) -> bool:
    return os.path.basename(argv0).lower() in ALLOWED_RUYI_ENTRYPOINT_NAMES


def should_prompt_for_renaming(argv0: str) -> bool:
    # We need to allow things like "ruyi-qemu" through, to not break our mux.
    # Only consider filenames starting with both our name *and* version to be
    # un-renamed onefile artifacts that warrant a rename prompt.
    likely_artifact_name_prefix = f"{RUYI_ENTRYPOINT_NAME}-{RUYI_SEMVER}."
    return os.path.basename(argv0).lower().startswith(likely_artifact_name_prefix)


def is_version_query(argv: list[str]) -> bool:
    # Scan flags broadly for issue #453, while only accepting the subcommand
    # spelling in command position so positional values named "version" do not
    # suppress OOBE/telemetry for unrelated commands.
    for arg in argv[1:]:
        if arg in VERSION_QUERY_FLAGS:
            return True

    for arg in argv[1:]:
        if arg == "--porcelain":
            continue
        return arg == VERSION_QUERY_SUBCOMMAND

    return False


def main(gm: GlobalModeProvider, gc: GlobalConfig, argv: list[str]) -> int:
    logger = gc.logger
    is_completion_script_invocation = is_cli_completion_script_requested(argv)
    is_ruyi_invocation = is_called_as_ruyi(gm.argv0)
    # Version queries must be side-effect-free: issue #453 showed that OOBE
    # could otherwise prompt before printing the version and consume first-run
    # telemetry state.
    skip_telemetry = is_ruyi_invocation and is_version_query(argv)

    # do not init telemetry or OOBE on shell completion invocations, because
    # our output isn't meant for humans in that case, and a "real" invocation
    # will likely follow shortly after
    if (
        not gm.is_cli_autocomplete
        and not is_completion_script_invocation
        and not skip_telemetry
    ):
        oobe = OOBE(gc)

        tm = gc.telemetry
        tm.check_first_run_status()
        tm.init_installation(False)
        atexit.register(tm.flush)
        oobe.handlers.append(tm.oobe_prompt)

        oobe.maybe_prompt()

    if not is_ruyi_invocation:
        if should_prompt_for_renaming(gm.argv0):
            logger.F(
                _(
                    "the {ruyi_exe} executable must be named [green]'{expected_name}'[/] to work"
                ).format(
                    ruyi_exe=RUYI_ENTRYPOINT_NAME,
                    expected_name=RUYI_ENTRYPOINT_NAME,
                )
            )
            logger.I(
                _("it is now [yellow]'{current_name}'[/]").format(
                    current_name=gm.argv0,
                )
            )
            logger.I(_("please rename the command file and retry"))
            return 1

        from ..mux.runtime import mux_main

        # record an invocation and the command name being proxied to
        gc.telemetry.record(
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

        # Pass NoneCompleter as the default so argcomplete produces no
        # suggestions of its own for arguments that lack a custom ruyi
        # completer.  The completion script then adds shell-native file
        # completions as a fallback.
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
        logger.F(_("internal error: CLI entrypoint was added without a telemetry key"))
        return 1

    # Special-case the `--output-completion-script` argument; treat it as if
    # "ruyi completion-script" were called.
    completion_script: str | None = getattr(args, "completion_script", None)
    if is_completion_script_invocation and completion_script is not None:
        return func(gc, args)

    if not skip_telemetry:
        tm = gc.telemetry
        tm.print_telemetry_notice()

        # Do not record `ruyi telemetry --cron-upload` invocations.
        skip_recording_invocation = telemetry_key == "telemetry" and getattr(
            args,
            "cron_upload",
            False,
        )
        if not skip_recording_invocation:
            tm.record(
                TelemetryScope(None),
                "cli:invocation-v1",
                key=telemetry_key,
            )

    return func(gc, args)
