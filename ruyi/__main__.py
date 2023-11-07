#!/usr/bin/env python

if __name__ == "__main__":
    import sys
    from ruyi import record_self_exe
    from ruyi.cli import main

    # note down our own executable path, for identity-checking in mux
    record_self_exe(__file__)

    sys.exit(main(sys.argv))
