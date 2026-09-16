import pathlib
import tomllib

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.abi import scan_source
from ruyi.ruyipkg.abi.serialize import dump_abi_report_toml
from ruyi.ruyipkg.abi.sources import ABISource
from tests.ruyipkg.abi._elfbuilder import build_elf


def _report(tmp_path: pathlib.Path, logger: RuyiLogger):  # type: ignore[no-untyped-def]
    (tmp_path / "a").write_bytes(build_elf(e_machine=62))
    (tmp_path / "r").write_bytes(build_elf(e_machine=243))
    return scan_source(ABISource.from_directory(tmp_path), logger=logger)


def test_deterministic(tmp_path: pathlib.Path, ruyi_logger: RuyiLogger) -> None:
    report = _report(tmp_path, ruyi_logger)
    assert dump_abi_report_toml(report) == dump_abi_report_toml(report)


def test_roundtrips_to_valid_toml(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    report = _report(tmp_path, ruyi_logger)
    text = dump_abi_report_toml(report)
    parsed = tomllib.loads(text)
    assert parsed["summary"]["elf_count"] == 2
    assert sorted(parsed["summary"]["e_machines"]) == [62, 243]
    assert len(parsed["record"]) == 2
    assert "sha256" in parsed["record"][0]


def test_empty_parsed_attrs_still_present(
    tmp_path: pathlib.Path, ruyi_logger: RuyiLogger
) -> None:
    (tmp_path / "u").write_bytes(build_elf(e_machine=0x9999))
    report = scan_source(ABISource.from_directory(tmp_path), logger=ruyi_logger)
    parsed = tomllib.loads(dump_abi_report_toml(report))
    assert parsed["record"][0]["parsed_attrs"] == {}
    assert parsed["record"][0]["e_machine"] == 0x9999
