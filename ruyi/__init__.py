_is_debug = False


def set_debug(v: bool):
    global _is_debug
    _is_debug = v


def is_debug() -> bool:
    return _is_debug


_self_exe: str = ""


def self_exe() -> str:
    return _self_exe


def record_self_exe(x: str) -> None:
    global _self_exe
    _self_exe = x


# This is true if we're packaged
IS_PACKAGED = False
