#!/usr/bin/env python3

if __name__ == "__main__":
    import sys
    import ruyi
    from ruyi import log

    if ruyi.is_running_as_root() and not ruyi.is_env_var_truthy(
        ruyi.ENV_FORCE_ALLOW_ROOT
    ):
        log.F("refusing to run as super user without explicit consent")

        choices = ", ".join(f"'{x}'" for x in ruyi.TRUTHY_ENV_VAR_VALUES)
        log.I(
            f"re-run with environment variable [yellow]{ruyi.ENV_FORCE_ALLOW_ROOT}[/] set to one of [yellow]{choices}[/] to signify consent"
        )
        sys.exit(1)

    ruyi.init_debug_status()

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

    from ruyi.cli import main
    from ruyi.cli.nuitka import get_nuitka_self_exe

    if not sys.argv:
        log.F("no argv?")
        sys.exit(1)

    # note down our own executable path, for identity-checking in mux, if not
    # we're not already Nuitka-compiled
    #
    # we assume the one-file build if Nuitka is detected; sys.argv[0] does NOT
    # work if it's just `ruyi` so we have to check our parent process in that case
    if hasattr(ruyi, "__compiled__"):
        ruyi.IS_PACKAGED = True
        log.D(
            f"__file__ = {__file__}, sys.executable = {sys.executable}, __compiled__ = {ruyi.__compiled__}"
        )
        self_exe = get_nuitka_self_exe()
    else:
        self_exe = __file__

    log.D(f"argv[0] = {sys.argv[0]}, self_exe = {self_exe}")
    ruyi.record_self_exe(sys.argv[0], self_exe)

    sys.exit(main(sys.argv))
