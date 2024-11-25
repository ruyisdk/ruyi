import platform
import sys
from typing import NamedTuple


class RuyiHost(NamedTuple):
    os: str
    arch: str

    def __str__(self) -> str:
        return f"{self.os}/{self.arch}"

    def canonicalize(self) -> "RuyiHost":
        return RuyiHost(
            os=canonicalize_os_str(self.os),
            arch=canonicalize_arch_str(self.arch),
        )


def canonicalize_host_str(host: str | RuyiHost) -> str:
    if isinstance(host, str):
        frags = host.split("/", 1)
        os = "linux" if len(frags) == 1 else frags[0]
        arch = frags[0] if len(frags) == 1 else frags[1]
        return str(RuyiHost(os, arch).canonicalize())

    return str(host.canonicalize())


def canonicalize_arch_str(arch: str) -> str:
    # Information sources:
    #
    # * https://bugs.python.org/issue7146#msg94134
    # * https://superuser.com/questions/305901/possible-values-of-processor-architecture
    match arch.lower():
        case "amd64" | "em64t":
            return "x86_64"
        case "arm64":
            return "aarch64"
        case "x86":
            return "i686"
        case arch_lower:
            return arch_lower


def canonicalize_os_str(os: str) -> str:
    match os:
        case "win32":
            return "windows"
        case _:
            return os


def get_native_host() -> RuyiHost:
    return RuyiHost(os=sys.platform, arch=platform.machine()).canonicalize()
