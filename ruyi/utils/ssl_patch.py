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
        return orig_paths

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


def _query_linux_system_ssl_default_cert_paths(
    soname: str | None = None,
) -> tuple[str, str, str, str]:
    if soname is None:
        # check libcrypto instead of libssl, because if the system libssl is
        # newer than the bundled one, the system libssl will depend on the
        # bundled libcrypto that may lack newer ELF symbol version(s). The
        # functions actually reside in libcrypto, after all.
        for soname in ("libcrypto.so", "libcrypto.so.3", "libcrypto.so.1.1"):
            try:
                return _query_linux_system_ssl_default_cert_paths(soname)
            except OSError as e:
                log.D(f"soname {soname} not working: {e}")
                continue

        # cannot proceed without certificates info (pygit2 initialization is
        # bound to fail anyway)
        log.F("cannot find the system libcrypto")
        log.I("TLS certificates and library are required for Ruyi to function")
        raise SystemExit(1)

    # dlopen-ing the bare soname will get us the system library
    lib = ctypes.CDLL(soname)
    lib.X509_get_default_cert_file_env.restype = ctypes.c_void_p
    lib.X509_get_default_cert_file.restype = ctypes.c_void_p
    lib.X509_get_default_cert_dir_env.restype = ctypes.c_void_p
    lib.X509_get_default_cert_dir.restype = ctypes.c_void_p

    result = (
        _decode_fsdefault_or_none(lib.X509_get_default_cert_file_env()),
        _decode_fsdefault_or_none(lib.X509_get_default_cert_file()),
        _decode_fsdefault_or_none(lib.X509_get_default_cert_dir_env()),
        _decode_fsdefault_or_none(lib.X509_get_default_cert_dir()),
    )

    log.D(f"got defaults from system libcrypto {soname}")
    log.D(f"X509_get_default_cert_file_env() = {result[0]}")
    log.D(f"X509_get_default_cert_file() = {result[1]}")
    log.D(f"X509_get_default_cert_dir_env() = {result[2]}")
    log.D(f"X509_get_default_cert_dir() = {result[3]}")

    return result


ssl.get_default_verify_paths = get_system_ssl_default_verify_paths
