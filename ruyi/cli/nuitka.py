import os


def get_nuitka_self_exe() -> str:
    # Assume we're a Nuitka onefile build, so our parent process is the onefile
    # bootstrap process. The onefile bootstrapper puts "our path" in the
    # undocumented environment variable $NUITKA_ONEFILE_BINARY, which works
    # on both Linux and Windows.
    return os.environ["NUITKA_ONEFILE_BINARY"]
