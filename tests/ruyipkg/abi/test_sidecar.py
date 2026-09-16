from __future__ import annotations

import pathlib
import tarfile

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.abi import dump_abi_report_toml
from ruyi.ruyipkg.abi.sidecar import (
    SIDECAR_SUFFIX,
    is_scannable,
    scan_path,
    sidecar_path_for,
    write_sidecar,
)
from tests.ruyipkg.abi._elfbuilder import build_elf


def test_sidecar_path_appends_suffix() -> None:
    p = pathlib.Path("/out/foo-1.0.tar.gz")
    assert sidecar_path_for(p) == pathlib.Path("/out/foo-1.0.tar.gz" + SIDECAR_SUFFIX)


def test_is_scannable_directory(tmp_path: pathlib.Path) -> None:
    assert is_scannable(tmp_path) is True


def test_is_scannable_tar(tmp_path: pathlib.Path) -> None:
    assert is_scannable(tmp_path / "pkg.tar.gz") is True


def test_is_scannable_zip_and_deb(tmp_path: pathlib.Path) -> None:
    assert is_scannable(tmp_path / "pkg.zip") is True
    assert is_scannable(tmp_path / "pkg.deb") is True


def test_is_scannable_unrecognized(tmp_path: pathlib.Path) -> None:
    assert is_scannable(tmp_path / "foo.sha256") is False
    assert is_scannable(tmp_path / "foo.txt") is False


def _make_tar(path: pathlib.Path) -> None:
    elf = build_elf(e_machine=243)
    member = path.parent / "bin_r"
    member.write_bytes(elf)
    with tarfile.open(path, mode="w") as tf:
        tf.add(member, arcname="bin/r")


def test_scan_path_and_write_sidecar_roundtrip(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    archive = tmp_path / "pkg.tar"
    _make_tar(archive)

    report = scan_path(ruyi_logger, archive)
    assert report.summary.elf_count == 1
    assert report.summary.e_machines == (243,)

    out = sidecar_path_for(archive)
    write_sidecar(report, out)
    assert out.read_text(encoding="utf-8") == dump_abi_report_toml(report)


def test_scan_path_directory_with_exclude(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    (tmp_path / "keep").mkdir()
    (tmp_path / "drop").mkdir()
    (tmp_path / "keep" / "a").write_bytes(build_elf(e_machine=62))
    (tmp_path / "drop" / "b").write_bytes(build_elf(e_machine=243))
    report = scan_path(ruyi_logger, tmp_path, exclude=["drop/**"])
    assert report.summary.e_machines == (62,)
    assert report.summary.excluded_count == 1
