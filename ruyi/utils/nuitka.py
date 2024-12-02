import os
import sys


def get_nuitka_self_exe() -> str:
    try:
        # Assume we're a Nuitka onefile build, so our parent process is the onefile
        # bootstrap process. The onefile bootstrapper puts "our path" in the
        # undocumented environment variable $NUITKA_ONEFILE_BINARY, which works
        # on both Linux and Windows.
        return os.environ["NUITKA_ONEFILE_BINARY"]
    except KeyError:
        # It seems we are instead launched from the extracted onefile tempdir.
        # Assume our name is "ruyi" in this case; directory is available in
        # Nuitka metadata.
        import ruyi

        return os.path.join(ruyi.__compiled__.containing_dir, "ruyi")


def get_argv0() -> str:
    import ruyi

    try:
        if ruyi.__compiled__.original_argv0 is not None:
            return ruyi.__compiled__.original_argv0
    except AttributeError:
        # Either we're not packaged with Nuitka, or the Nuitka used is
        # without our original_argv0 patch, in which case we cannot do any
        # better than simply returning sys.argv[0].
        pass

    return sys.argv[0]
