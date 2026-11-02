"""Tests for the shared test-environment helpers."""

from __future__ import annotations

import builtins
import platform

from pytest import MonkeyPatch

from tests.helpers import has_proc_cpuinfo, has_supported_libc


def test_has_proc_cpuinfo_is_false_when_unreadable(
    monkeypatch: MonkeyPatch,
) -> None:
    def denied(*args: object, **kwargs: object) -> None:
        raise PermissionError("denied by sandbox")

    monkeypatch.setattr(builtins, "open", denied)

    assert has_proc_cpuinfo() is False


def test_has_supported_libc_accepts_glibc(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(platform, "libc_ver", lambda: ("glibc", "2.39"))

    assert has_supported_libc() is True
