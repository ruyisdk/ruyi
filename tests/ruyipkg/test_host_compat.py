import pathlib

import pytest
from pytest import MonkeyPatch

import ruyi.ruyipkg.host_compat as host_compat
from ruyi.ruyipkg.host_compat import (
    HostCompatProblem,
    HostCompatStatus,
    PackageHostCompat,
    format_problem,
)


@pytest.fixture(autouse=True)
def _identity_gettext(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(host_compat, "_", lambda s: s)


def test_status_markup() -> None:
    assert HostCompatStatus.Unchecked.as_rich_markup() == "unchecked"
    assert HostCompatStatus.NoABIInfo.as_rich_markup() == "[dim]no ABI info[/]"
    assert (
        HostCompatStatus.LikelyCompatible.as_rich_markup()
        == "[green]likely compatible[/]"
    )
    assert (
        HostCompatStatus.LikelyIncompatible.as_rich_markup()
        == "[red]likely incompatible[/]"
    )
    assert (
        HostCompatStatus.CompatibilityUnknown.as_rich_markup()
        == "[yellow]compatibility unknown[/]"
    )


def test_package_host_compat_to_porcelain() -> None:
    compat = PackageHostCompat(
        HostCompatStatus.LikelyIncompatible,
        problems=(
            HostCompatProblem(
                "e-machine",
                False,
                "package targets e_machine(s) {want}, host is {got}",
                {"want": [243], "got": [62]},
            ),
        ),
        sidecars=(pathlib.Path("/repo/_abi/pkg.tar.abi.toml"),),
    )

    assert compat.to_porcelain() == {
        "status": "likely-incompatible",
        "problems": [
            {
                "check": "e-machine",
                "compatible": False,
                "msgid": "package targets e_machine(s) {want}, host is {got}",
                "params": {"want": [243], "got": [62]},
            }
        ],
    }


def test_format_problem() -> None:
    problem = HostCompatProblem(
        "soname",
        None,
        "could not locate shared library {soname} on this host",
        {"soname": "libc.so.6"},
    )

    assert (
        format_problem(problem)
        == "soname: could not locate shared library libc.so.6 on this host"
    )
