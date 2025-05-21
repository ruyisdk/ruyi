import os
import typing


_argv0: str = ""
_main_file: str = ""
_self_exe: str = ""


def argv0() -> str:
    return _argv0


def main_file() -> str:
    return _main_file


def self_exe() -> str:
    return _self_exe


def record_self_exe(argv0: str, main_file: str, x: str) -> None:
    global _argv0
    global _main_file
    global _self_exe
    _argv0 = argv0
    _main_file = main_file
    _self_exe = x


def is_running_as_root() -> bool:
    # this is way too simplistic but works on *nix systems which is all we
    # support currently
    if hasattr(os, "getuid"):
        return os.getuid() == 0
    return False


# This is true if we're packaged
IS_PACKAGED = False

if typing.TYPE_CHECKING:

    class NuitkaVersion(typing.NamedTuple):
        major: int
        minor: int
        micro: int
        releaselevel: str
        containing_dir: str
        standalone: bool
        onefile: bool
        macos_bundle_mode: bool
        no_asserts: bool
        no_docstrings: bool
        no_annotations: bool
        module: bool
        main: str
        original_argv0: str | None

    __compiled__: NuitkaVersion
