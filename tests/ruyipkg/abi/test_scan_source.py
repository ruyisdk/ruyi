import pathlib

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.abi import scan_source
from ruyi.ruyipkg.abi.sources import ABISource
from tests.ruyipkg.abi._elfbuilder import build_elf


def _write_tree(tmp_path: pathlib.Path) -> None:
    x86 = build_elf(e_machine=62)
    riscv = build_elf(e_machine=243)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "a").write_bytes(x86)
    (tmp_path / "bin" / "a-copy").write_bytes(x86)  # identical -> dedup
    (tmp_path / "bin" / "r").write_bytes(riscv)
    (tmp_path / "readme.txt").write_bytes(b"not an elf")
    excluded = tmp_path / "excluded"
    excluded.mkdir()
    (excluded / "fixture").write_bytes(x86)


def test_scan_source_dedup_exclude_and_counts(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    _write_tree(tmp_path)
    report = scan_source(
        ABISource.from_directory(tmp_path),
        logger=ruyi_logger,
        exclude=["excluded/**"],
    )

    # Two distinct ELFs (x86 deduped across a + a-copy; plus riscv).
    assert report.summary.elf_count == 2
    assert sorted(report.summary.e_machines) == [62, 243]
    assert report.summary.excluded_count == 1

    # The x86 record lists both paths, sorted.
    x86_rec = next(r for r in report.records if r.e_machine == 62)
    assert x86_rec.paths == ("bin/a", "bin/a-copy")

    # readme.txt counted as inspected but not an ELF; excluded/ not counted.
    # file_count = a, a-copy, r, readme.txt = 4
    assert report.summary.file_count == 4


def test_records_sorted_by_sha(tmp_path: pathlib.Path, ruyi_logger: RuyiLogger) -> None:
    _write_tree(tmp_path)
    report = scan_source(ABISource.from_directory(tmp_path), logger=ruyi_logger)
    shas = [r.sha256 for r in report.records]
    assert shas == sorted(shas)
