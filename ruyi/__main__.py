#!/usr/bin/env python

if __name__ == "__main__":
    import sys
    import ruyi
    from ruyi import log
    from ruyi.cli import init_debug_status, main
    from ruyi.cli.nuitka import get_nuitka_self_exe

    init_debug_status()

    if not sys.argv:
        log.F("no argv?")
        sys.exit(1)

    # note down our own executable path, for identity-checking in mux, if not
    # we're not already Nuitka-compiled
    #
    # we assume the one-file build if Nuitka is detected; sys.argv[0] does NOT
    # work if it's just `ruyi` so we have to check our parent process in that case
    if hasattr(ruyi, "__compiled__"):
        self_exe = get_nuitka_self_exe()
        ruyi.IS_PACKAGED = True
    else:
        self_exe = __file__

    log.D(f"argv[0] = {sys.argv[0]}, self_exe = {self_exe}")
    ruyi.record_self_exe(sys.argv[0], self_exe)

    sys.exit(main(sys.argv))
