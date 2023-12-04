_is_debug = False


def set_debug(v: bool):
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
