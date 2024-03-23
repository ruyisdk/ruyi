import typing

_is_debug = False


def set_debug(v: bool) -> None:
    global _is_debug
    _is_debug = v


def is_debug() -> bool:
    return _is_debug


_argv0: str = ""
_self_exe: str = ""


def argv0() -> str:
    return _argv0


def self_exe() -> str:
    return _self_exe


def record_self_exe(argv0: str, x: str) -> None:
    global _argv0
    global _self_exe
    _argv0 = argv0
    _self_exe = x


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

    __compiled__: NuitkaVersion
