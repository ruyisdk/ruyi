"""CLI integration tests for `ruyi admin rescan-package-abi`."""

from __future__ import annotations

import pathlib
import tarfile

from tests.fixtures import IntegrationTestHarness
from tests.ruyipkg.abi._elfbuilder import build_elf


def _make_tar(tmp_path: pathlib.Path, name: str = "pkg.tar") -> pathlib.Path:
    member = tmp_path / "_r"
    member.write_bytes(build_elf(e_machine=243))
    archive = tmp_path / name
    with tarfile.open(archive, mode="w") as tf:
        tf.add(member, arcname="bin/r")
    return archive


def test_rescan_writes_sidecar_by_default(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    archive = _make_tar(tmp_path)
    result = ruyi_cli_runner("admin", "rescan-package-abi", str(archive))
    assert result.exit_code == 0, result.stderr
    sidecar = archive.with_name(archive.name + ".abi.toml")
    assert sidecar.is_file()
    assert "[summary]" in sidecar.read_text(encoding="utf-8")


def test_rescan_stdout_dash(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    archive = _make_tar(tmp_path)
    result = ruyi_cli_runner("admin", "rescan-package-abi", str(archive), "-o", "-")
    assert result.exit_code == 0, result.stderr
    assert "[summary]" in result.stdout
    assert not archive.with_name(archive.name + ".abi.toml").exists()


def test_rescan_explicit_output_file(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    archive = _make_tar(tmp_path)
    dest = tmp_path / "report.toml"
    result = ruyi_cli_runner(
        "admin", "rescan-package-abi", str(archive), "-o", str(dest)
    )
    assert result.exit_code == 0, result.stderr
    assert dest.is_file()
    assert "[summary]" in dest.read_text(encoding="utf-8")


def test_rescan_directory_input(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    tree = tmp_path / "tree"
    (tree / "bin").mkdir(parents=True)
    (tree / "bin" / "r").write_bytes(build_elf(e_machine=243))
    result = ruyi_cli_runner("admin", "rescan-package-abi", str(tree), "-o", "-")
    assert result.exit_code == 0, result.stderr
    assert "e_machines = [243]" in result.stdout


def test_rescan_exclude_from_file(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    tree = tmp_path / "tree"
    (tree / "keep").mkdir(parents=True)
    (tree / "drop").mkdir(parents=True)
    (tree / "keep" / "a").write_bytes(build_elf(e_machine=62))
    (tree / "drop" / "b").write_bytes(build_elf(e_machine=243))
    patterns = tmp_path / "ex.txt"
    patterns.write_text("# skip built test dir\ndrop/**\n", encoding="utf-8")
    result = ruyi_cli_runner(
        "admin", "rescan-package-abi", str(tree), "--exclude", f"@{patterns}", "-o", "-"
    )
    assert result.exit_code == 0, result.stderr
    assert "e_machines = [62]" in result.stdout


def test_rescan_unrecognized_path_errors(
    tmp_path: pathlib.Path, ruyi_cli_runner: IntegrationTestHarness
) -> None:
    bogus = tmp_path / "foo.sha256"
    bogus.write_text("deadbeef\n", encoding="utf-8")
    result = ruyi_cli_runner("admin", "rescan-package-abi", str(bogus))
    assert result.exit_code != 0
