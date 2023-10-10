#!/usr/bin/env python

if __name__ == '__main__':
    import sys
    from ruyi.cli import main, record_self_exe

    # note down our own executable path, for identity-checking in mux
    record_self_exe(__file__)

    sys.exit(main(sys.argv))
