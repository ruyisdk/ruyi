"""Shared test-environment helpers."""

from __future__ import annotations

import pathlib
import platform
import sys

import pytest


def has_proc_cpuinfo() -> bool:
    """Return whether /proc/cpuinfo is readable on this host."""
    try:
        with open("/proc/cpuinfo", "rb") as fp:
            fp.read(1)
    except OSError:
        return False
    return True


def has_supported_libc() -> bool:
    """Return whether the host libc is one the ABI prober supports."""
    libc, _ = platform.libc_ver()
    if libc in ("glibc", "musl"):
        return True

    # platform.libc_ver() cannot identify every musl installation.
    return any(pathlib.Path("/lib").glob("ld-musl-*.so.1"))


requires_linux_procfs = pytest.mark.skipif(
    sys.platform != "linux" or not has_proc_cpuinfo(),
    reason="requires readable Linux /proc/cpuinfo",
)

requires_supported_libc = pytest.mark.skipif(
    sys.platform != "linux" or not has_supported_libc(),
    reason="requires Linux with glibc or musl",
)
