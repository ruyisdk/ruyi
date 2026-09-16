import dataclasses

import pytest

from ruyi.ruyipkg.abi.model import (
    ABIReport,
    ABIScanError,
    ABISummary,
    AttributeVendorBlob,
    ElfABIRecord,
    ElfType,
    GnuProperty,
    VersionNeed,
)


def test_elftype_values() -> None:
    assert ElfType.DYN == "dyn"  # type: ignore[comparison-overlap]
    assert ElfType("rel") is ElfType.REL


def test_record_is_frozen() -> None:
    rec = ElfABIRecord(
        paths=("bin/x",),
        sha256="abc",
        e_machine=243,
        elf_class=64,
        endianness="little",
        elf_type=ElfType.DYN,
        is_dynamic=True,
        interpreter=None,
        soname=None,
        needed=("libc.so.6",),
        version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.34",)),),
        needs_unversioned=False,
        gnu_properties=(GnuProperty(0xC0008002, "07000000", False),),
        elf_attributes=(AttributeVendorBlob("riscv", "41", False),),
        parsed_attrs={"isa": "rv64gc"},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.sha256 = "xyz"  # type: ignore[misc]


def test_report_composition() -> None:
    summary = ABISummary(
        e_machines=(243,),
        needed=("libc.so.6",),
        version_needs=(),
        well_known_maxima={},
        parsed_attrs_rollup={},
        elf_count=0,
        file_count=0,
        excluded_count=0,
    )
    report = ABIReport(records=(), summary=summary, errors=(ABIScanError("p", "bad"),))
    assert report.errors[0].reason == "bad"
