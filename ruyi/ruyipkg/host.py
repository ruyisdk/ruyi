import platform
import sys


def canonicalize_host_str(host: str) -> str:
    return host if "/" in host else f"linux/{host}"


def canonicalize_os_str(os: str) -> str:
    match os:
        case "win32":
            return "windows"
        case _:
            return os


def get_native_host() -> str:
    return f"{canonicalize_os_str(sys.platform)}/{platform.machine()}"
