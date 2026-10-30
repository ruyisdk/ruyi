"""Host reading primitives for interpreter host_attrs() implementations.

Every function swallows I/O and OS errors and returns an empty value:
probing must degrade, never raise.
"""

from __future__ import annotations


def read_cpuinfo(path: str = "/proc/cpuinfo") -> str:
    try:
        with open(path, encoding="utf-8") as fp:
            return fp.read()
    except OSError:
        return ""


def read_auxv() -> dict[int, int]:
    """Return selected auxv entries via getauxval(3); empty on failure.

    Look the symbol up in the running process first, so that musl (which has
    no ``libc.so.6`` compatibility name) is handled like glibc. Fall back to
    the glibc soname for environments where the process symbol is hidden.
    """
    import ctypes

    getauxval = None
    for name in (None, "libc.so.6"):
        try:
            libc = ctypes.CDLL(name)
            getauxval = libc.getauxval
            getauxval.restype = ctypes.c_ulong
            break
        except (AttributeError, OSError):
            getauxval = None
    if getauxval is None:
        return {}
    out: dict[int, int] = {}
    for at in (16, 26):  # AT_HWCAP, AT_HWCAP2
        try:
            out[at] = int(getauxval(ctypes.c_ulong(at)))
        except Exception:  # noqa: BLE001, S110
            pass
    return out
