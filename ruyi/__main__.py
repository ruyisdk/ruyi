#!/usr/bin/env python3

import os
import sys

import ruyi
from ruyi.utils.ci import is_running_in_ci
from ruyi.utils.global_mode import (
    EnvGlobalModeProvider,
    ENV_FORCE_ALLOW_ROOT,
    TRUTHY_ENV_VAR_VALUES,
    is_env_var_truthy,
)
from ruyi.utils.node_info import probe_for_container_runtime

# NOTE: no imports that directly or indirectly pull in pygit2 should go here,
# because import of pygit2 will fail if done before ssl_patch. Notably this
# means no GlobalConfig here because it depends on ruyi.ruyipkg.repo.


def _is_running_as_root() -> bool:
    # this is way too simplistic but works on *nix systems which is all we
    # support currently
    if hasattr(os, "getuid"):
        return os.getuid() == 0
    return False


def _is_allowed_to_run_as_root() -> bool:
    if is_env_var_truthy(os.environ, ENV_FORCE_ALLOW_ROOT):
        return True
    if is_running_in_ci(os.environ):
        # CI environments are usually considered to be controlled, and safe
        # for root usage.
        return True
    if probe_for_container_runtime(os.environ) != "unknown":
        # So are container environments.
        return True
    return False


def entrypoint() -> None:
    gm = EnvGlobalModeProvider(os.environ, sys.argv)

    # NOTE: import of `ruyi.log` takes ~90ms on my machine, so initialization
    # of logging is deferred as late as possible

    if _is_running_as_root() and not _is_allowed_to_run_as_root():
        from ruyi.log import RuyiConsoleLogger

        logger = RuyiConsoleLogger(gm)

        logger.F("refusing to run as super user outside CI without explicit consent")

        choices = ", ".join(f"'{x}'" for x in TRUTHY_ENV_VAR_VALUES)
        logger.I(
            f"re-run with environment variable [yellow]{ENV_FORCE_ALLOW_ROOT}[/] set to one of [yellow]{choices}[/] to signify consent"
        )
        sys.exit(1)

    if not sys.argv:
        from ruyi.log import RuyiConsoleLogger

        logger = RuyiConsoleLogger(gm)

        logger.F("no argv?")
        sys.exit(1)

    if gm.is_packaged and ruyi.__compiled__.standalone:
        # If we're running from a bundle, our bundled libssl may remember a
        # different path for loading certificates than appropriate for the
        # current system, in which case the pygit2 import will fail. To avoid
        # this we have to patch ssl.get_default_verify_paths with additional
        # logic.
        #
        # this must happen before pygit2 is imported
        from ruyi.utils import ssl_patch

        del ssl_patch

    from ruyi.utils.nuitka import get_nuitka_self_exe, get_argv0

    # note down our own executable path, for identity-checking in mux, if not
    # we're not already Nuitka-compiled
    #
    # we assume the one-file build if Nuitka is detected; sys.argv[0] does NOT
    # work if it's just `ruyi` so we have to check our parent process in that case
    self_exe = get_nuitka_self_exe() if gm.is_packaged else __file__
    sys.argv[0] = get_argv0()
    gm.record_self_exe(sys.argv[0], __file__, self_exe)

    from ruyi.config import GlobalConfig
    from ruyi.cli.main import main
    from ruyi.log import RuyiConsoleLogger

    logger = RuyiConsoleLogger(gm)
    gc = GlobalConfig.load_from_config(gm, logger)
    sys.exit(main(gm, gc, sys.argv))


if __name__ == "__main__":
    entrypoint()
