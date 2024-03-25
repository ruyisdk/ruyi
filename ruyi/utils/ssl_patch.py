import ctypes
import os
import ssl
import sys
from typing import NamedTuple

from .. import log

_orig_get_default_verify_paths = ssl.get_default_verify_paths
_cached_paths: ssl.DefaultVerifyPaths | None = None


def get_system_ssl_default_verify_paths() -> ssl.DefaultVerifyPaths:
    global _cached_paths

    if _cached_paths is None:
        _cached_paths = _get_system_ssl_default_verify_paths()
    return _cached_paths


def _get_system_ssl_default_verify_paths() -> ssl.DefaultVerifyPaths:
    orig_paths = _orig_get_default_verify_paths()
    if sys.platform != "linux":
        return orig_paths

    result: ssl.DefaultVerifyPaths | None = None

    # imitate the stdlib flow but with overridden data source
    try:
        parts = _query_linux_system_ssl_default_cert_paths()
        if parts is None:
            log.W("failed to probe system libcrypto")
        else:
            result = to_ssl_paths(parts)
    except Exception as e:
        log.D(f"cannot get system libcrypto default cert paths: {e}")

    if result is None:
        log.D("falling back to probing hard-coded paths")
        result = probe_fallback_verify_paths()

    if result is None:
        # cannot proceed without certificates info (pygit2 initialization is
        # bound to fail anyway)
        log.F("cannot find the system libcrypto and/or TLS certificates")
        log.I("TLS certificates and library are required for Ruyi to function")
        raise SystemExit(1)

    if result != orig_paths:
        log.D(
            "get_default_verify_paths() values differ between bundled and system libssl"
        )
        log.D(f"bundled: {orig_paths}")
        log.D(f" system: {result}")

    return result


def to_ssl_paths(parts: tuple[str, str, str, str]) -> ssl.DefaultVerifyPaths | None:
    cafile = os.environ.get(parts[0], parts[1])
    capath = os.environ.get(parts[2], parts[3])

    is_cafile_present = os.path.isfile(cafile)
    is_capath_present = os.path.isdir(capath)
    if not is_cafile_present and not is_capath_present:
        return None

    # must do "else None" like the stdlib, despite the type annotation being just "str"
    return ssl.DefaultVerifyPaths(
        cafile if is_cafile_present else None,  # type: ignore[arg-type]
        capath if is_capath_present else None,  # type: ignore[arg-type]
        *parts,
    )


def _decode_fsdefault_or_none(val: int | None) -> str:
    if val is None:
        return ""

    s = ctypes.c_char_p(val)
    if s.value is None:
        return ""

    return s.value.decode(sys.getfilesystemencoding())


def _query_linux_system_ssl_default_cert_paths(
    soname: str | None = None,
) -> tuple[str, str, str, str] | None:
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

        return None

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


class WellKnownCALocation(NamedTuple):
    cafile: str
    capath: str


WELL_KNOWN_CA_LOCATIONS: list[WellKnownCALocation] = [
    # Most others
    WellKnownCALocation("/etc/ssl/cert.pem", "/etc/ssl/certs"),
    # Debian-based distros
    WellKnownCALocation("/usr/lib/ssl/cert.pem", "/usr/lib/ssl/certs"),
    # RPM-based distros
    WellKnownCALocation("/etc/pki/tls/cert.pem", "/etc/pki/tls/certs"),
]


def probe_fallback_verify_paths() -> ssl.DefaultVerifyPaths | None:
    for loc in WELL_KNOWN_CA_LOCATIONS:
        is_file_present = os.path.isfile(loc.cafile)
        is_dir_present = os.path.isdir(loc.capath)
        if not is_file_present and not is_dir_present:
            continue

        return ssl.DefaultVerifyPaths(
            loc.cafile if is_file_present else None,  # type: ignore[arg-type]
            loc.capath if is_dir_present else None,  # type: ignore[arg-type]
            "SSL_CERT_FILE",
            loc.cafile,
            "SSL_CERT_DIR",
            loc.capath,
        )

    return None


ssl.get_default_verify_paths = get_system_ssl_default_verify_paths
