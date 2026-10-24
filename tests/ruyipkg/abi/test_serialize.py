import pathlib
import tomllib

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.abi import scan_source
from ruyi.ruyipkg.abi.model import ABIReport, ABISummary, ElfABIRecord, ElfType
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


def _record_for(version_defs: tuple[str, ...]) -> ElfABIRecord:
    return ElfABIRecord(
        paths=("bin/x",),
        sha256="0" * 64,
        e_machine=62,
        elf_class=64,
        endianness="little",
        elf_type=ElfType.DYN,
        is_dynamic=True,
        interpreter=None,
        soname=None,
        needed=(),
        version_needs=(),
        version_defs=version_defs,
        needs_unversioned=False,
        gnu_properties=(),
        elf_attributes=(),
        parsed_attrs={},
    )


def _report_for(version_defs: tuple[str, ...]) -> ABIReport:
    summary = ABISummary(
        e_machines=(62,),
        needed=(),
        version_needs=(),
        well_known_maxima={},
        parsed_attrs_rollup={},
        elf_count=1,
        file_count=1,
        excluded_count=0,
    )
    return ABIReport(records=(_record_for(version_defs),), summary=summary, errors=())


def test_version_defs_serialized_when_present() -> None:
    text = dump_abi_report_toml(_report_for(("GLIBC_2.34",)))
    assert 'version_defs = ["GLIBC_2.34"]' in text


def test_version_defs_omitted_when_empty() -> None:
    text = dump_abi_report_toml(_report_for(()))
    assert "version_defs" not in text
