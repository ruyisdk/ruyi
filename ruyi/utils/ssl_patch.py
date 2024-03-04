import ctypes
import os
import ssl
import sys

from .. import log

_orig_get_default_verify_paths = ssl.get_default_verify_paths
_cached_paths: ssl.DefaultVerifyPaths | None = None


def get_system_ssl_default_verify_paths() -> ssl.DefaultVerifyPaths:
    global _cached_paths

    orig_paths = _orig_get_default_verify_paths()
    if sys.platform != "linux":
        return orig_paths

    if _cached_paths is not None:
        return _cached_paths

    # imitate the stdlib flow but with overridden data source
    try:
        parts = _query_linux_system_ssl_default_cert_paths()
    except Exception as e:
        log.D(f"cannot get system libssl default cert paths: {e}")
        return _orig_get_default_verify_paths()

    cafile = os.environ.get(parts[0], parts[1])
    capath = os.environ.get(parts[2], parts[3])

    # must do "else None" like the stdlib, despite the type annotation being just "str"
    result = ssl.DefaultVerifyPaths(
        cafile if os.path.isfile(cafile) else None,  # type: ignore[arg-type]
        capath if os.path.isdir(capath) else None,  # type: ignore[arg-type]
        *parts,
    )

    if result != orig_paths:
        log.D(
            "get_default_verify_paths() values differ between bundled and system libssl"
        )
        log.D(f"bundled: {orig_paths}")
        log.D(f" system: {result}")

    _cached_paths = result
    return result


def _decode_fsdefault_or_none(val: int | None) -> str:
    if val is None:
        return ""

    s = ctypes.c_char_p(val)
    if s.value is None:
        return ""

    return s.value.decode(sys.getfilesystemencoding())


def _query_linux_system_ssl_default_cert_paths() -> tuple[str, str, str, str]:
    # this can work because right now Nuitka packages the libssl as "libssl.so.X"
    # notice the presence of sover suffix
    # so dlopen-ing "libssl.so" will get us the system library
    libssl = ctypes.CDLL("libssl.so")
    libssl.X509_get_default_cert_file_env.restype = ctypes.c_void_p
    libssl.X509_get_default_cert_file.restype = ctypes.c_void_p
    libssl.X509_get_default_cert_dir_env.restype = ctypes.c_void_p
    libssl.X509_get_default_cert_dir.restype = ctypes.c_void_p

    return (
        _decode_fsdefault_or_none(libssl.X509_get_default_cert_file_env()),
        _decode_fsdefault_or_none(libssl.X509_get_default_cert_file()),
        _decode_fsdefault_or_none(libssl.X509_get_default_cert_dir_env()),
        _decode_fsdefault_or_none(libssl.X509_get_default_cert_dir()),
    )


ssl.get_default_verify_paths = get_system_ssl_default_verify_paths
