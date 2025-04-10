import os
import typing

TRUTHY_ENV_VAR_VALUES: typing.Final = {"1", "true", "x", "y", "yes"}


def is_env_var_truthy(var: str) -> bool:
    if v := os.environ.get(var):
        return v.lower() in TRUTHY_ENV_VAR_VALUES
    return False


ENV_DEBUG: typing.Final = "RUYI_DEBUG"
ENV_EXPERIMENTAL: typing.Final = "RUYI_EXPERIMENTAL"
ENV_FORCE_ALLOW_ROOT: typing.Final = "RUYI_FORCE_ALLOW_ROOT"


_is_debug = False
_is_experimental = False
_is_porcelain = False


def set_porcelain(v: bool) -> None:
    global _is_porcelain
    _is_porcelain = v


def is_debug() -> bool:
    return _is_debug


def is_experimental() -> bool:
    return _is_experimental


def is_porcelain() -> bool:
    return _is_porcelain


def init_debug_status() -> None:
    global _is_debug
    global _is_experimental
    _is_debug = is_env_var_truthy(ENV_DEBUG)
    _is_experimental = is_env_var_truthy(ENV_EXPERIMENTAL)


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
