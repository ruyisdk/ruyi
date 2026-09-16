from ruyi.ruyipkg.abi.aggregate import build_summary
from ruyi.ruyipkg.abi.model import ElfABIRecord, ElfType, VersionNeed


def _rec(**kw: object) -> ElfABIRecord:
    base: dict[str, object] = dict(
        paths=("x",),
        sha256="0",
        e_machine=62,
        elf_class=64,
        endianness="little",
        elf_type=ElfType.DYN,
        is_dynamic=True,
        interpreter=None,
        soname=None,
        needed=(),
        version_needs=(),
        needs_unversioned=False,
        gnu_properties=(),
        elf_attributes=(),
        parsed_attrs={},
    )
    base.update(kw)
    return ElfABIRecord(**base)  # type: ignore[arg-type]


def test_needed_union_sorted() -> None:
    recs = [_rec(needed=("libm.so.6",)), _rec(needed=("libc.so.6", "libm.so.6"))]
    summary = build_summary(recs, file_count=2, excluded_count=0)
    assert summary.needed == ("libc.so.6", "libm.so.6")


def test_well_known_maxima_picks_highest_glibc() -> None:
    recs = [
        _rec(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.17", "GLIBC_2.34")),)),
        _rec(version_needs=(VersionNeed("libc.so.6", ("GLIBC_2.9", "GLIBC_2.28")),)),
    ]
    summary = build_summary(recs, file_count=2, excluded_count=0)
    assert summary.well_known_maxima["GLIBC"] == "2.34"


def test_rollup_x86_minimum_level() -> None:
    recs = [
        _rec(e_machine=62, parsed_attrs={"isa_level": "v3"}),
        _rec(e_machine=62, parsed_attrs={"isa_level": "v2"}),
    ]
    summary = build_summary(recs, file_count=2, excluded_count=0)
    assert summary.parsed_attrs_rollup["62"] == {
        "isa_level": "v2",
        "isa_levels": ["v2", "v3"],
    }


def test_counts_passthrough() -> None:
    summary = build_summary([_rec()], file_count=5, excluded_count=3)
    assert summary.elf_count == 1
    assert summary.file_count == 5
    assert summary.excluded_count == 3
    assert summary.e_machines == (62,)
