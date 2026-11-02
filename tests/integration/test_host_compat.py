"""Integration tests for host compatibility in list and install."""

from __future__ import annotations

import json
from typing import Any, cast

from pytest import MonkeyPatch

from ruyi.ruyipkg.abi import ABIReport, ElfABIRecord, ElfType
from ruyi.ruyipkg.abi.aggregate import build_summary
from ruyi.ruyipkg.abi.serialize import dump_abi_report_toml
from ruyi.ruyipkg.distfile import Distfile
from ruyi.ruyipkg.host import get_native_host

from tests.fixtures import IntegrationTestHarness


def _record(e_machine: int) -> ElfABIRecord:
    return ElfABIRecord(
        paths=("bin/x",),
        sha256="0" * 64,
        e_machine=e_machine,
        elf_class=64,
        endianness="little",
        elf_type=ElfType.DYN,
        is_dynamic=True,
        interpreter=None,
        soname=None,
        needed=(),
        version_needs=(),
        version_defs=(),
        needs_unversioned=False,
        gnu_properties=(),
        elf_attributes=(),
        parsed_attrs={},
    )


def _report(e_machine: int) -> ABIReport:
    record = _record(e_machine)
    return ABIReport(
        records=(record,),
        summary=build_summary((record,), file_count=1, excluded_count=0),
        errors=(),
    )


def _add_binary_package(
    runner: IntegrationTestHarness,
    *,
    host: str,
    distfile: str = "abi-cli.tar",
) -> None:
    manifest = f"""\
format = "v1"

[metadata]
desc = "ABI test package"
vendor = {{ name = "test", eula = "" }}

[[distfiles]]
name = "{distfile}"
size = 0

[distfiles.checksums]
sha256 = "{"0" * 64}"

[[binary]]
host = "{host}"
distfiles = ["{distfile}"]
"""
    runner.add_package("dev-tools", "abi-cli", "1.0.0", manifest)


def _write_sidecar(
    runner: IntegrationTestHarness,
    *,
    distfile: str,
    e_machine: int,
) -> None:
    sidecar = (
        runner.repo_root
        / "packages"
        / "dev-tools"
        / "abi-cli"
        / "_abi"
        / f"{distfile}.abi.toml"
    )
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text(
        dump_abi_report_toml(_report(e_machine)),
        encoding="utf-8",
    )


def _other_e_machine() -> int:
    return 243 if get_native_host().arch != "riscv64" else 62


def test_list_shows_incompatible_status_when_probing_is_allowed(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    native = get_native_host()
    _add_binary_package(ruyi_cli_runner, host=native.arch)
    _write_sidecar(
        ruyi_cli_runner,
        distfile="abi-cli.tar",
        e_machine=_other_e_machine(),
    )

    result = ruyi_cli_runner("list", "--all", "--allow-probing-host")

    assert result.exit_code == 0
    # The console renders markup away when stdout is not a terminal, so the
    # captured output carries the human-readable status text.
    assert "likely incompatible" in result.stdout


def test_porcelain_reports_unchecked_without_flag_and_status_with_flag(
    ruyi_cli_runner: IntegrationTestHarness,
) -> None:
    native = get_native_host()
    _add_binary_package(ruyi_cli_runner, host=native.arch)
    _write_sidecar(
        ruyi_cli_runner,
        distfile="abi-cli.tar",
        e_machine=_other_e_machine(),
    )

    unchecked = ruyi_cli_runner("--porcelain", "list", "--all")
    checked = ruyi_cli_runner(
        "--porcelain",
        "list",
        "--all",
        "--allow-probing-host",
    )

    def _pkg_version(result_stdout: str, name: str) -> dict[str, Any]:
        objects = [
            json.loads(line) for line in result_stdout.splitlines() if line.strip()
        ]
        pkg = next(
            o for o in objects if o["ty"] == "pkglistoutput-v1" and o["name"] == name
        )
        return cast(dict[str, Any], pkg["vers"][0])

    assert unchecked.exit_code == 0
    assert checked.exit_code == 0
    assert _pkg_version(unchecked.stdout, "abi-cli")["host_compat"] == {
        "status": "unchecked",
        "problems": [],
    }
    assert (
        _pkg_version(checked.stdout, "abi-cli")["host_compat"]["status"]
        == "likely-incompatible"
    )


def test_install_warns_but_continues_on_incompatible_package(
    ruyi_cli_runner: IntegrationTestHarness,
    monkeypatch: MonkeyPatch,
) -> None:
    native = get_native_host()
    _add_binary_package(ruyi_cli_runner, host=native.arch)
    _write_sidecar(
        ruyi_cli_runner,
        distfile="abi-cli.tar",
        e_machine=_other_e_machine(),
    )
    monkeypatch.setattr(Distfile, "ensure", lambda self, logger: None)
    monkeypatch.setattr(
        "ruyi.ruyipkg.install.ensure_unpack_cmd_for_method",
        lambda logger, method: None,
    )

    result = ruyi_cli_runner("install", "--fetch-only", "abi-cli")

    assert result.exit_code == 0
    assert "e-machine" in result.stderr


def test_install_can_disable_probing(
    ruyi_cli_runner: IntegrationTestHarness,
    monkeypatch: MonkeyPatch,
) -> None:
    native = get_native_host()
    _add_binary_package(ruyi_cli_runner, host=native.arch)
    _write_sidecar(
        ruyi_cli_runner,
        distfile="abi-cli.tar",
        e_machine=_other_e_machine(),
    )
    monkeypatch.setattr(Distfile, "ensure", lambda self, logger: None)
    monkeypatch.setattr(
        "ruyi.ruyipkg.install.ensure_unpack_cmd_for_method",
        lambda logger, method: None,
    )

    result = ruyi_cli_runner(
        "install",
        "--fetch-only",
        "--no-allow-probing-host",
        "abi-cli",
    )

    assert result.exit_code == 0
    assert "e-machine" not in result.stderr
