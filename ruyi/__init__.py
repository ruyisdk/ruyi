import os
import typing

TRUTHY_ENV_VAR_VALUES = {"1", "true", "x", "y", "yes"}


def is_env_var_truthy(var: str) -> bool:
    if v := os.environ.get(var):
        return v.lower() in TRUTHY_ENV_VAR_VALUES
    return False


ENV_DEBUG = "RUYI_DEBUG"
ENV_FORCE_ALLOW_ROOT = "RUYI_FORCE_ALLOW_ROOT"


_is_debug = False


def set_debug(v: bool) -> None:
    global _is_debug
    _is_debug = v


def is_debug() -> bool:
    return _is_debug


def init_debug_status() -> None:
    set_debug(is_env_var_truthy(ENV_DEBUG))


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

    __compiled__: NuitkaVersion
