"""Real-world smoke tests for the ELF ABI scanner.

These scan genuine distfiles from the RuyiSDK software repository (``wlink``),
covering the three production architectures, and pin both the decoded ABI
facts and the canonical serialization output. The fixtures are large, but the
scanner streams archive members without extracting them, so the tests stay
fast.
"""

from __future__ import annotations

import pytest

from ruyi.log import RuyiLogger
from ruyi.ruyipkg.abi import ABISource, dump_abi_report_toml, scan_source
from ruyi.ruyipkg.abi.model import ElfType
from tests.fixtures import RuyiFileFixtureFactory

_FIXTURE_PREFIX = "wlink-0.1.2-ruyi.20260501"

# (arch, expected e_machine)
_CASES = [
    ("aarch64", 183),
    ("riscv64", 243),
    ("x86_64", 62),
]


@pytest.mark.parametrize(("arch", "e_machine"), _CASES)
def test_scans_real_distfile_facts(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    arch: str,
    e_machine: int,
) -> None:
    with ruyi_file.path(
        "ruyipkg_suites", "abi", f"{_FIXTURE_PREFIX}.{arch}.tar.gz"
    ) as archive:
        report = scan_source(ABISource.from_archive(archive), logger=ruyi_logger)

    assert report.errors == ()
    assert report.summary.elf_count == 1
    assert report.summary.file_count == 1
    assert report.summary.e_machines == (e_machine,)

    assert len(report.records) == 1
    record = report.records[0]
    assert record.e_machine == e_machine
    assert record.elf_class == 64
    assert record.endianness == "little"
    assert any(path.endswith("bin/wlink") for path in record.paths)

    if arch == "aarch64":
        assert record.parsed_attrs == {"bti": False, "pac": False}
        assert record.is_dynamic is False
        assert record.elf_type == ElfType.EXEC
    elif arch == "riscv64":
        assert str(record.parsed_attrs["isa"]).startswith("rv64i2p1")
        assert record.parsed_attrs["stack_align"] == 16
        assert {attr.vendor for attr in record.elf_attributes} == {"riscv"}
        assert all(not attr.truncated for attr in record.elf_attributes)
    else:  # x86_64
        assert record.parsed_attrs["isa_level"] == "v1"
        assert record.is_dynamic is True
        assert record.elf_type == ElfType.DYN


@pytest.mark.parametrize("arch", [case[0] for case in _CASES])
def test_real_distfile_serialization_matches_golden(
    ruyi_file: RuyiFileFixtureFactory,
    ruyi_logger: RuyiLogger,
    arch: str,
) -> None:
    with ruyi_file.path(
        "ruyipkg_suites", "abi", f"{_FIXTURE_PREFIX}.{arch}.tar.gz"
    ) as archive:
        report = scan_source(ABISource.from_archive(archive), logger=ruyi_logger)

    with ruyi_file.path(
        "ruyipkg_suites", "abi", f"{_FIXTURE_PREFIX}.{arch}.expected.toml"
    ) as golden:
        expected = golden.read_text(encoding="utf-8")

    assert dump_abi_report_toml(report) == expected
