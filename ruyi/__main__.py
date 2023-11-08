#!/usr/bin/env python

if __name__ == "__main__":
    import os.path
    import sys
    import ruyi
    from ruyi.cli import main

    # note down our own executable path, for identity-checking in mux
    # we assume the one-file build if Nuitka is detected
    self_exe = (
        os.path.abspath(sys.argv[0]) if hasattr(ruyi, "__compiled__") else __file__
    )
    ruyi.record_self_exe(self_exe)

    sys.exit(main(sys.argv))
