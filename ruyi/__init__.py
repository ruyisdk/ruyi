_is_debug = False

def set_debug(v: bool):
    global _is_debug
    _is_debug = v

def is_debug() -> bool:
    return _is_debug
