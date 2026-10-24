"""CLI integration tests for `ruyi admin check-abi`."""

from __future__ import annotations

import pathlib
import shutil

from tests.fixtures import IntegrationTestHarness, RuyiFileFixtureFactory


def _build_sidecar(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
    ruyi_file: RuyiFileFixtureFactory,
    *,
    arch: str,
) -> pathlib.Path:
    prefix = "wlink-0.1.2-ruyi.20260501"
    archive_name = f"{prefix}.{arch}.tar.gz"

    # Copy out of the tracked fixture tree so the default sidecar does not
    # pollute the repository checkout.
    with ruyi_file.path("ruyipkg_suites", "abi", archive_name) as fixture:
        archive = tmp_path / fixture.name
        shutil.copyfile(fixture, archive)

    result = ruyi_cli_runner("admin", "rescan-package-abi", str(archive))
    assert result.exit_code == 0, result.stderr

    sidecar = archive.with_name(archive.name + ".abi.toml")
    assert sidecar.is_file()
    return sidecar


def test_check_abi_cross_arch_reports_problem(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
    ruyi_file: RuyiFileFixtureFactory,
) -> None:
    from ruyi.ruyipkg.host import get_native_host

    host_arch = get_native_host().arch
    # Pick a fixture that is not the host arch so a definite e-machine
    # mismatch is produced regardless of where the test runs.
    fixture_archs = ("riscv64", "aarch64", "x86_64")
    cross_arch = next((a for a in fixture_archs if a != host_arch), "riscv64")

    sidecar = _build_sidecar(tmp_path, ruyi_cli_runner, ruyi_file, arch=cross_arch)

    result = ruyi_cli_runner("admin", "check-abi", str(sidecar))
    assert result.exit_code == 1
    assert "e-machine" in result.stdout


def test_check_abi_matching_arch_is_clean(
    tmp_path: pathlib.Path,
    ruyi_cli_runner: IntegrationTestHarness,
    ruyi_file: RuyiFileFixtureFactory,
) -> None:
    from ruyi.ruyipkg.host import get_native_host

    host_arch = get_native_host().arch
    if host_arch not in ("riscv64", "aarch64", "x86_64"):
        return

    sidecar = _build_sidecar(tmp_path, ruyi_cli_runner, ruyi_file, arch=host_arch)

    result = ruyi_cli_runner("admin", "check-abi", str(sidecar))
    assert result.exit_code == 0


def test_check_abi_missing_sidecar_errors(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    missing = tmp_path / "nope.abi.toml"
    result = ruyi_cli_runner("admin", "check-abi", str(missing))
    assert result.exit_code == 1
    assert "Traceback" not in result.stderr
