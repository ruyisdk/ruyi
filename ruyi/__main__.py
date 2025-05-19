#!/usr/bin/env python3

import os
import sys

import ruyi
from ruyi.utils.ci import is_running_in_ci
# NOTE: no imports that directly or indirectly pull in pygit2 should go here,
# because import of pygit2 will fail if done before ssl_patch. Notably this
# means no GlobalConfig here because it depends on ruyi.ruyipkg.repo.


def is_allowed_to_run_as_root() -> bool:
    if ruyi.is_env_var_truthy(ruyi.ENV_FORCE_ALLOW_ROOT):
        return True
    if is_running_in_ci(os.environ):
        # CI environments are usually considered to be controlled, and safe
        # for root usage.
        return True
    return False


def entrypoint() -> None:
    from ruyi.log import RuyiLogger

    logger = RuyiLogger()

    if ruyi.is_running_as_root() and not is_allowed_to_run_as_root():
        logger.F("refusing to run as super user outside CI without explicit consent")

        choices = ", ".join(f"'{x}'" for x in ruyi.TRUTHY_ENV_VAR_VALUES)
        logger.I(
            f"re-run with environment variable [yellow]{ruyi.ENV_FORCE_ALLOW_ROOT}[/] set to one of [yellow]{choices}[/] to signify consent"
        )
        sys.exit(1)

    ruyi.init_debug_status()

    if not sys.argv:
        logger.F("no argv?")
        sys.exit(1)

    if hasattr(ruyi, "__compiled__") and ruyi.__compiled__.standalone:
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
    if hasattr(ruyi, "__compiled__"):
        ruyi.IS_PACKAGED = True
        self_exe = get_nuitka_self_exe()
    else:
        self_exe = __file__

    sys.argv[0] = get_argv0()
    ruyi.record_self_exe(sys.argv[0], __file__, self_exe)

    from ruyi.config import GlobalConfig
    from ruyi.cli.main import main

    gc = GlobalConfig.load_from_config(logger)
    sys.exit(main(gc, sys.argv))


if __name__ == "__main__":
    entrypoint()
